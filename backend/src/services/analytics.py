from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from time import perf_counter
from typing import Any

from src.core.settings import get_settings
from src.db.models.analytics_reports import AnalyticsReport
from src.db.models.documents import Document
from src.db.models.project_milestones import ProjectMilestone, ProjectMilestoneStatus
from src.db.models.project_stages import ProjectStage
from src.db.models.project_stickers import ProjectSticker
from src.db.models.projects import Project
from src.db.models.task_activity import TaskActivity
from src.db.models.task_comments import TaskComment
from src.db.models.task_dependencies import TaskDependency
from src.db.models.tasks import Task
from src.db.models.users import User
from src.db.models.wbs_nodes import WbsNode
from src.exceptions.analytics import (
    AnalyticsEmptyScopeError,
    AnalyticsGenerationError,
    AnalyticsReportsRepositoryError,
    AnalyticsServiceError,
)
from src.exceptions.document_links import DocumentLinksRepositoryError
from src.exceptions.documents import DocumentsRepositoryError
from src.exceptions.knowledge import KnowledgeProviderError
from src.exceptions.milestones import MilestonesRepositoryError
from src.exceptions.project_stages import ProjectStagesRepositoryError
from src.exceptions.project_stickers import ProjectStickersRepositoryError
from src.exceptions.projects import ProjectNotFoundError, ProjectsRepositoryError
from src.exceptions.task_activity import TaskActivityRepositoryError
from src.exceptions.task_comments import TaskCommentsRepositoryError
from src.exceptions.task_dependencies import TaskDependenciesRepositoryError
from src.exceptions.tasks import TasksRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.exceptions.wbs_nodes import WbsNodesRepositoryError
from src.knowledge.runtime import KnowledgeRuntime, get_knowledge_runtime
from src.repositories.analytics_reports import AnalyticsReportsRepository
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.project_stickers import ProjectStickersRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.task_dependencies import TaskDependenciesRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.wbs_nodes import WbsNodesRepository
from src.schemas.analytics import (
    AnalyticsContextSchema,
    AnalyticsDraftSchema,
    AnalyticsFindingSchema,
    AnalyticsHealth,
    AnalyticsProgressSchema,
    AnalyticsRecommendationSchema,
    AnalyticsReportSchema,
    AnalyticsScope,
    AnalyticsSignalsSchema,
    AnalyticsTaskRefSchema,
)
from src.services.prompts.analytics import ANALYTICS_SYSTEM_PROMPT
from src.services.tasks import build_task_key
from src.utils.deadlines import DUE_SOON_DAYS, is_task_due_soon, is_task_overdue

logger = logging.getLogger(__name__)

MAX_COMPLETION_TOKENS = 6000
# Порог, за которым срез перестраивается по ужатым лимитам. Считаем в символах:
# точный подсчёт токенов потребовал бы токенизатора конкретной модели, а нам
# нужна лишь защита от контекста, который модель не примет целиком.
MAX_CONTEXT_CHARS = 90_000
STALE_TASK_DAYS = 14
DESCRIPTION_TASKS_LIMIT = 25
NAME_LIMIT = 302

RepositoryErrors = (
    AnalyticsReportsRepositoryError,
    DocumentLinksRepositoryError,
    DocumentsRepositoryError,
    MilestonesRepositoryError,
    ProjectStagesRepositoryError,
    ProjectStickersRepositoryError,
    ProjectsRepositoryError,
    TaskActivityRepositoryError,
    TaskCommentsRepositoryError,
    TaskDependenciesRepositoryError,
    TasksRepositoryError,
    UnitOfWorkRepositoryError,
    WbsNodesRepositoryError,
)


@dataclass(frozen=True, slots=True)
class _Limits:
    """Сколько данных каждого вида помещается в один срез для модели."""

    tasks: int
    comments_per_task: int
    comment_chars: int
    documents: int
    document_chars: int
    stickers: int
    sticker_chars: int
    activity: int
    description_chars: int


# Проектный анализ тратит весь бюджет на один проект, портфельный делит его
# между всеми: иначе один крупный проект вытеснит из среза остальные.
PROJECT_LIMITS = _Limits(
    tasks=180,
    comments_per_task=3,
    comment_chars=500,
    documents=12,
    document_chars=1200,
    stickers=40,
    sticker_chars=400,
    activity=50,
    description_chars=400,
)
PORTFOLIO_LIMITS = _Limits(
    tasks=60,
    comments_per_task=2,
    comment_chars=350,
    documents=4,
    document_chars=500,
    stickers=15,
    sticker_chars=280,
    activity=20,
    description_chars=250,
)


@dataclass(slots=True)
class _ProjectSlice:
    """Сырые данные одного проекта, из которых собирается срез для модели."""

    project: Project
    stages: list[ProjectStage]
    tasks: list[Task]
    comments: dict[int, list[TaskComment]]
    activity: list[TaskActivity]
    dependencies: list[TaskDependency]
    nodes: list[WbsNode]
    milestones: list[ProjectMilestone]
    stickers: list[ProjectSticker]
    documents: list[Document]
    document_task_ids: dict[int, list[int]] = field(default_factory=dict)


class AnalyticsService:
    """Аналитический свод дашборда: разбор состояния работ моделью.

    Сервис ничего не меняет в проектах. Он собирает срез рабочего пространства,
    просит модель объяснить, что в нём важно, сверяет ответ с реальными
    задачами и сохраняет результат, чтобы свод не пропадал при перезагрузке
    страницы.
    """

    def __init__(
        self,
        reports_repository: AnalyticsReportsRepository,
        projects_repository: ProjectsRepository,
        members_repository: ProjectMembersRepository,
        stages_repository: ProjectStagesRepository,
        tasks_repository: TasksRepository,
        comments_repository: TaskCommentsRepository,
        activity_repository: TaskActivityRepository,
        dependencies_repository: TaskDependenciesRepository,
        wbs_nodes_repository: WbsNodesRepository,
        milestones_repository: MilestonesRepository,
        stickers_repository: ProjectStickersRepository,
        documents_repository: DocumentsRepository,
        document_links_repository: DocumentLinksRepository,
        unit_of_work: UnitOfWork,
        runtime: KnowledgeRuntime | None = None,
    ):
        self.reports_repository = reports_repository
        self.projects_repository = projects_repository
        self.members_repository = members_repository
        self.stages_repository = stages_repository
        self.tasks_repository = tasks_repository
        self.comments_repository = comments_repository
        self.activity_repository = activity_repository
        self.dependencies_repository = dependencies_repository
        self.wbs_nodes_repository = wbs_nodes_repository
        self.milestones_repository = milestones_repository
        self.stickers_repository = stickers_repository
        self.documents_repository = documents_repository
        self.document_links_repository = document_links_repository
        self.unit_of_work = unit_of_work
        self.runtime = runtime or get_knowledge_runtime()

    async def get_latest(
        self,
        *,
        user_id: int,
        project_id: int | None,
    ) -> AnalyticsReportSchema | None:
        """Возвращает последний сохранённый свод выбранной области.

        Args:
            user_id: Идентификатор пользователя.
            project_id: Проект анализа; ``None`` — весь портфель пользователя.

        Returns:
            Последний свод или ``None``, если анализ ещё не запускали.

        Raises:
            ProjectNotFoundError: Если проект недоступен пользователю.
            AnalyticsServiceError: Если прочитать свод не удалось.
        """
        try:
            allowed_ids = await self.members_repository.get_project_ids_for_user(user_id=user_id)
            if project_id is not None:
                if project_id not in allowed_ids:
                    raise ProjectNotFoundError(project_id=project_id)
                report = await self.reports_repository.get_latest_for_project(project_id=project_id)
            else:
                report = await self.reports_repository.get_latest_portfolio(user_id=user_id)
        except RepositoryErrors as error:
            logger.error("❌ Ошибка чтения аналитического свода.", exc_info=True)
            raise AnalyticsServiceError(str(error)) from error

        if report is None:
            return None
        return _to_report_schema(report=report, project=report.project)

    async def generate(self, *, user: User, project_id: int | None) -> AnalyticsReportSchema:
        """Формирует новый аналитический свод по проекту или всему портфелю.

        Args:
            user: Пользователь, запросивший анализ.
            project_id: Проект анализа; ``None`` — весь портфель пользователя.

        Returns:
            Сформированный и сохранённый свод.

        Raises:
            ProjectNotFoundError: Если проект недоступен пользователю.
            AnalyticsEmptyScopeError: Если в выбранной области нет задач.
            KnowledgeProviderError: Если LLM-сервис недоступен.
            AnalyticsGenerationError: Если ответ модели непригоден.
            AnalyticsServiceError: Если собрать данные не удалось.
        """
        started_at = perf_counter()
        today = date.today()
        scope = AnalyticsScope.PROJECT if project_id is not None else AnalyticsScope.PORTFOLIO

        try:
            projects = await self._resolve_projects(user_id=user.id, project_id=project_id)
            slices = [
                await self._collect_project(project=project, scope=scope) for project in projects
            ]
        except RepositoryErrors as error:
            logger.error("❌ Ошибка сбора данных для аналитического свода.", exc_info=True)
            raise AnalyticsServiceError(str(error)) from error

        if not any(project_slice.tasks for project_slice in slices):
            raise AnalyticsEmptyScopeError(
                error_details=f"В области анализа (project_id={project_id}) нет задач.",
            )

        signals = _build_signals(slices=slices, today=today)
        content, context = _build_content(slices=slices, scope=scope, signals=signals, today=today)

        try:
            draft = await self.runtime.llm_client.get_structured_response(
                system_prompt=ANALYTICS_SYSTEM_PROMPT,
                content=content,
                schema=AnalyticsDraftSchema,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
            )
        except KnowledgeProviderError:
            raise
        except Exception as error:
            logger.error("❌ Модель не вернула аналитический свод.", exc_info=True)
            raise AnalyticsGenerationError(str(error)) from error

        payload = _resolve_draft(draft=draft, slices=slices, today=today)
        duration_ms = round((perf_counter() - started_at) * 1000)

        try:
            report = await self.reports_repository.save(
                data={
                    "project_id": project_id,
                    "created_by_user_id": user.id,
                    "created_by_display_name_snapshot": _display_name(user),
                    "llm_model": get_settings().llm.agent_model,
                    "duration_ms": duration_ms,
                    "payload": payload | {"signals": signals.model_dump(mode="json")},
                    "context_summary": context.model_dump(mode="json"),
                }
            )
            await self.unit_of_work.commit()
        except RepositoryErrors as error:
            await self.unit_of_work.rollback()
            logger.error("❌ Не удалось сохранить аналитический свод.", exc_info=True)
            raise AnalyticsServiceError(str(error)) from error

        logger.info(
            "🤖 Аналитический свод %s: проектов %s, задач в контексте %s, находок %s, %s мс.",
            scope.value,
            context.projects,
            context.tasks_included,
            len(payload["findings"]),
            duration_ms,
        )
        return _to_report_schema(
            report=report,
            project=slices[0].project if scope is AnalyticsScope.PROJECT else None,
        )

    async def _resolve_projects(self, *, user_id: int, project_id: int | None) -> list[Project]:
        """Возвращает проекты области анализа с проверкой доступа."""
        allowed_ids = await self.members_repository.get_project_ids_for_user(user_id=user_id)
        if project_id is not None:
            if project_id not in allowed_ids:
                # Чужой проект неотличим от несуществующего: наличие чужих
                # данных не подтверждается (см. правила доступа проекта).
                raise ProjectNotFoundError(project_id=project_id)
            project = await self.projects_repository.get_by_id(project_id=project_id)
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            return [project]

        projects = [
            project
            for project in await self.projects_repository.get_all()
            if project.id in allowed_ids
        ]
        if not projects:
            raise AnalyticsEmptyScopeError(
                error_details=f"У пользователя id={user_id} нет доступных проектов.",
            )
        return projects

    async def _collect_project(self, *, project: Project, scope: AnalyticsScope) -> _ProjectSlice:
        """Загружает всё, что относится к одному проекту анализа."""
        limits = PROJECT_LIMITS if scope is AnalyticsScope.PROJECT else PORTFOLIO_LIMITS
        stages = await self.stages_repository.get_by_project(project_id=project.id)
        tasks = await self.tasks_repository.get_by_project(project_id=project.id)
        activity = await self.activity_repository.get_recent_by_project(
            project_id=project.id,
            limit=limits.activity,
        )
        dependencies = await self.dependencies_repository.get_by_project(project_id=project.id)
        nodes = await self.wbs_nodes_repository.get_by_project(project_id=project.id)
        milestones = await self.milestones_repository.get_by_project(project_id=project.id)
        stickers = await self.stickers_repository.list_by_project_id(project_id=project.id)
        documents = await self.documents_repository.get_by_project(project_id=project.id)

        # Комментарии берём только к задачам, которые попадут в срез: у
        # проекта с сотнями закрытых задач остальные всё равно не пригодятся.
        selected_tasks = _select_tasks(
            tasks=tasks,
            stages=stages,
            limit=limits.tasks,
            today=date.today(),
        )
        comments = await self.comments_repository.get_for_tasks(
            task_ids={task.id for task in selected_tasks}
        )
        comments_by_task: dict[int, list[TaskComment]] = {}
        for comment in comments:
            comments_by_task.setdefault(comment.task_id, []).append(comment)

        links = await self.document_links_repository.get_for_documents(
            document_ids={document.id for document in documents}
        )
        document_task_ids: dict[int, list[int]] = {}
        for link in links:
            document_task_ids.setdefault(link.document_id, []).append(link.task_id)

        return _ProjectSlice(
            project=project,
            stages=stages,
            tasks=tasks,
            comments=comments_by_task,
            activity=activity,
            dependencies=dependencies,
            nodes=nodes,
            milestones=milestones,
            stickers=stickers,
            documents=documents,
            document_task_ids=document_task_ids,
        )


# Блок расчёта фактов.


def _build_signals(slices: list[_ProjectSlice], today: date) -> AnalyticsSignalsSchema:
    """Считает проверяемые показатели по всей области анализа."""
    soon_until = today + timedelta(days=DUE_SOON_DAYS)
    stale_before = datetime.now(UTC) - timedelta(days=STALE_TASK_DAYS)
    totals = dict.fromkeys(
        (
            "total_tasks",
            "done_tasks",
            "overdue_tasks",
            "due_soon_tasks",
            "no_due_date_tasks",
            "unassigned_tasks",
            "stale_tasks",
            "blocked_tasks",
            "unplaced_tasks",
            "milestones_at_risk",
        ),
        0,
    )

    for project_slice in slices:
        done_stage_ids = _done_stage_ids(project_slice.stages)
        done_task_ids = {task.id for task in project_slice.tasks if task.stage_id in done_stage_ids}
        for task in project_slice.tasks:
            is_done = task.id in done_task_ids
            totals["total_tasks"] += 1
            if is_done:
                totals["done_tasks"] += 1
                continue
            if is_task_overdue(due_date=task.due_date, is_done=is_done, today=today):
                totals["overdue_tasks"] += 1
            if is_task_due_soon(
                due_date=task.due_date,
                is_done=is_done,
                today=today,
                soon_until=soon_until,
            ):
                totals["due_soon_tasks"] += 1
            if task.due_date is None:
                totals["no_due_date_tasks"] += 1
            if not task.assignee:
                totals["unassigned_tasks"] += 1
            if task.updated_at and task.updated_at < stale_before:
                totals["stale_tasks"] += 1
            if task.wbs_node_id is None:
                totals["unplaced_tasks"] += 1

        blocked_ids = {
            dependency.successor_task_id
            for dependency in project_slice.dependencies
            if dependency.predecessor_task_id not in done_task_ids
            and dependency.successor_task_id not in done_task_ids
        }
        totals["blocked_tasks"] += len(blocked_ids)
        totals["milestones_at_risk"] += sum(
            1
            for milestone in project_slice.milestones
            if milestone.status is not ProjectMilestoneStatus.ACHIEVED
            and milestone.due_date < today
        )

    return AnalyticsSignalsSchema(**totals)


# Блок сборки среза для модели.


def _build_content(
    slices: list[_ProjectSlice],
    scope: AnalyticsScope,
    signals: AnalyticsSignalsSchema,
    today: date,
) -> tuple[str, AnalyticsContextSchema]:
    """Собирает JSON-срез рабочего пространства и описание его границ.

    Срез сначала строится по полным лимитам; если он не влезает в бюджет
    контекста, пересобирается по ужатым. Так модель получает максимум данных,
    а пользователь — честное перечисление того, что в анализ не вошло.
    """
    base = PROJECT_LIMITS if scope is AnalyticsScope.PROJECT else PORTFOLIO_LIMITS
    payload, context = _render(
        slices=slices, limits=base, scope=scope, signals=signals, today=today
    )
    content = json.dumps(payload, ensure_ascii=False)
    if len(content) <= MAX_CONTEXT_CHARS:
        return content, context

    tight = _tighten(base)
    payload, context = _render(
        slices=slices,
        limits=tight,
        scope=scope,
        signals=signals,
        today=today,
    )
    context.omitted.append(
        "срез пересобран по ужатым лимитам: полный объём данных не помещается в контекст модели"
    )
    return json.dumps(payload, ensure_ascii=False), context


def _tighten(limits: _Limits) -> _Limits:
    """Вдвое ужимает срез, сильнее всего — документы: они самые объёмные."""
    return _Limits(
        tasks=max(limits.tasks // 2, 20),
        comments_per_task=max(limits.comments_per_task // 2, 1),
        comment_chars=max(limits.comment_chars // 2, 150),
        documents=max(limits.documents // 3, 2),
        document_chars=max(limits.document_chars // 3, 200),
        stickers=max(limits.stickers // 2, 5),
        sticker_chars=max(limits.sticker_chars // 2, 120),
        activity=max(limits.activity // 2, 10),
        description_chars=max(limits.description_chars // 2, 120),
    )


def _render(
    slices: list[_ProjectSlice],
    limits: _Limits,
    scope: AnalyticsScope,
    signals: AnalyticsSignalsSchema,
    today: date,
) -> tuple[dict[str, Any], AnalyticsContextSchema]:
    """Строит срез и статистику включённого по заданным лимитам."""
    soon_until = today + timedelta(days=DUE_SOON_DAYS)
    counts = dict.fromkeys(
        ("tasks", "comments", "documents", "stickers", "nodes", "milestones", "activity"),
        0,
    )
    omitted: list[str] = []
    rendered_projects: list[dict[str, Any]] = []

    for project_slice in slices:
        done_stage_ids = _done_stage_ids(project_slice.stages)
        stage_names = {stage.id: stage.name for stage in project_slice.stages}
        node_paths = _node_paths(project_slice.nodes)
        selected_tasks = _select_tasks(
            tasks=project_slice.tasks,
            stages=project_slice.stages,
            limit=limits.tasks,
            today=today,
        )
        blocked_by = _blocked_by(
            dependencies=project_slice.dependencies,
            done_stage_ids=done_stage_ids,
            tasks=project_slice.tasks,
            project_key=project_slice.project.key,
        )

        rendered_tasks = []
        for index, task in enumerate(selected_tasks):
            is_done = task.stage_id in done_stage_ids
            comments = project_slice.comments.get(task.id, [])[-limits.comments_per_task :]
            counts["comments"] += len(comments)
            entry: dict[str, Any] = {
                "key": build_task_key(project_key=project_slice.project.key, number=task.number),
                "title": task.title,
                "stage": stage_names.get(task.stage_id, "—"),
                "done": is_done,
                "priority": task.priority.value,
                "assignee": task.assignee or None,
                "role": task.role.value if task.role else None,
                "start": task.start_date.isoformat() if task.start_date else None,
                "due": task.due_date.isoformat() if task.due_date else None,
                "updated": task.updated_at.date().isoformat() if task.updated_at else None,
                "wbs": node_paths.get(task.wbs_node_id) if task.wbs_node_id else None,
            }
            if is_task_overdue(due_date=task.due_date, is_done=is_done, today=today):
                entry["overdue_days"] = (today - task.due_date).days
            if is_task_due_soon(
                due_date=task.due_date,
                is_done=is_done,
                today=today,
                soon_until=soon_until,
            ):
                entry["due_soon"] = True
            if task.id in blocked_by:
                entry["blocked_by"] = blocked_by[task.id]
            if index < DESCRIPTION_TASKS_LIMIT and task.description_md:
                entry["description"] = _cut(task.description_md, limits.description_chars)
            if comments:
                entry["comments"] = [
                    {
                        "when": comment.created_at.date().isoformat(),
                        "who": comment.author_name or "—",
                        "text": _cut(comment.body_md, limits.comment_chars),
                    }
                    for comment in comments
                ]
            rendered_tasks.append(entry)
        counts["tasks"] += len(rendered_tasks)

        selected_documents = _select_documents(
            documents=project_slice.documents,
            document_task_ids=project_slice.document_task_ids,
            limit=limits.documents,
        )
        task_keys_by_id = {
            task.id: build_task_key(project_key=project_slice.project.key, number=task.number)
            for task in project_slice.tasks
        }
        rendered_documents = [
            {
                "title": document.title,
                "linked_tasks": [
                    task_keys_by_id[task_id]
                    for task_id in project_slice.document_task_ids.get(document.id, [])
                    if task_id in task_keys_by_id
                ],
                "excerpt": _cut(document.content_md, limits.document_chars),
            }
            for document in selected_documents
        ]
        counts["documents"] += len(rendered_documents)

        rendered_stickers = [
            {
                "author": sticker.created_by_display_name_snapshot,
                "when": sticker.created_at.date().isoformat() if sticker.created_at else None,
                "text": _cut(sticker.body, limits.sticker_chars),
                "tasks": [
                    task_keys_by_id[link.task_id]
                    for link in sticker.task_links
                    if link.task_id in task_keys_by_id
                ],
            }
            for sticker in project_slice.stickers[: limits.stickers]
        ]
        counts["stickers"] += len(rendered_stickers)

        wbs_counts = _wbs_task_counts(project_slice.tasks)
        rendered_nodes = [
            f"{node_paths[node.id]} ({wbs_counts.get(node.id, 0)} задач)"
            for node in project_slice.nodes
            if node.id in node_paths
        ]
        counts["nodes"] += len(rendered_nodes)

        rendered_milestones = [
            {
                "title": milestone.title,
                "due": milestone.due_date.isoformat(),
                "status": milestone.status.value,
                "days_left": (milestone.due_date - today).days,
            }
            for milestone in project_slice.milestones
        ]
        counts["milestones"] += len(rendered_milestones)

        rendered_activity = [
            {
                "when": event.created_at.date().isoformat(),
                "task": task_keys_by_id.get(event.task_id, "—"),
                "event": event.event_type.value,
                "from": event.from_value,
                "to": event.to_value,
            }
            for event in project_slice.activity
            if event.task_id in task_keys_by_id
        ]
        counts["activity"] += len(rendered_activity)

        skipped_tasks = len(project_slice.tasks) - len(rendered_tasks)
        if skipped_tasks > 0:
            omitted.append(
                f"{project_slice.project.key}: в анализ вошли {len(rendered_tasks)} из "
                f"{len(project_slice.tasks)} задач — сначала просроченные, срочные и активные"
            )
        skipped_documents = len(project_slice.documents) - len(rendered_documents)
        if skipped_documents > 0:
            omitted.append(
                f"{project_slice.project.key}: разобраны {len(rendered_documents)} из "
                f"{len(project_slice.documents)} документов — приоритет у связанных с задачами"
            )

        rendered_projects.append(
            {
                "key": project_slice.project.key,
                "name": project_slice.project.name,
                "status": project_slice.project.status.value,
                "description": _cut(project_slice.project.description_md or "", 800) or None,
                "stages": [stage.name for stage in project_slice.stages],
                "wbs": rendered_nodes,
                "milestones": rendered_milestones,
                "tasks": rendered_tasks,
                "stickers": rendered_stickers,
                "documents": rendered_documents,
                "recent_activity": rendered_activity,
            }
        )

    payload = {
        "today": today.isoformat(),
        "scope": scope.value,
        "signals": signals.model_dump(mode="json"),
        "projects": rendered_projects,
    }
    context = AnalyticsContextSchema(
        projects=len(slices),
        tasks_total=sum(len(project_slice.tasks) for project_slice in slices),
        tasks_included=counts["tasks"],
        comments_included=counts["comments"],
        documents_included=counts["documents"],
        stickers_included=counts["stickers"],
        wbs_nodes_included=counts["nodes"],
        milestones_included=counts["milestones"],
        activity_included=counts["activity"],
        truncated=bool(omitted),
        omitted=omitted,
    )
    return payload, context


def _select_tasks(
    tasks: list[Task],
    stages: list[ProjectStage],
    limit: int,
    today: date,
) -> list[Task]:
    """Отбирает задачи для среза: сначала то, что требует решения.

    Порядок отбора и есть порядок важности: просроченные, затем срочные, затем
    остальные открытые по свежести, и только потом закрытые.
    """
    done_stage_ids = _done_stage_ids(stages)
    soon_until = today + timedelta(days=DUE_SOON_DAYS)

    def rank(task: Task) -> tuple[int, float]:
        is_done = task.stage_id in done_stage_ids
        if is_task_overdue(due_date=task.due_date, is_done=is_done, today=today):
            group = 0
        elif is_task_due_soon(
            due_date=task.due_date,
            is_done=is_done,
            today=today,
            soon_until=soon_until,
        ):
            group = 1
        elif not is_done:
            group = 2
        else:
            group = 3
        updated = task.updated_at.timestamp() if task.updated_at else 0.0
        return (group, -updated)

    return sorted(tasks, key=rank)[:limit]


def _select_documents(
    documents: list[Document],
    document_task_ids: dict[int, list[int]],
    limit: int,
) -> list[Document]:
    """Отбирает документы для среза, начиная со связанных с задачами.

    Документ, прикреплённый к задаче, почти всегда объясняет саму работу;
    остальные добираются следом, пока не исчерпан лимит.
    """
    ordered = sorted(
        documents,
        key=lambda document: (0 if document_task_ids.get(document.id) else 1, document.id),
    )
    return ordered[:limit]


def _done_stage_ids(stages: list[ProjectStage]) -> set[int]:
    """Возвращает идентификаторы завершающих стадий проекта."""
    return {stage.id for stage in stages if stage.is_done_stage}


def _node_paths(nodes: list[WbsNode]) -> dict[int, str]:
    """Строит номер и путь каждого раздела ИСР вида ``1.2 Проектирование``."""
    children: dict[int | None, list[WbsNode]] = {}
    for node in nodes:
        children.setdefault(node.parent_id, []).append(node)
    for group in children.values():
        group.sort(key=lambda node: (node.position, node.id))

    paths: dict[int, str] = {}

    def walk(parent_id: int | None, prefix: str) -> None:
        for index, node in enumerate(children.get(parent_id, []), start=1):
            number = f"{prefix}{index}"
            paths[node.id] = f"{number} {node.title}"
            walk(node.id, f"{number}.")

    walk(None, "")
    return paths


def _wbs_task_counts(tasks: list[Task]) -> dict[int, int]:
    """Считает число задач в каждом разделе ИСР."""
    counts: dict[int, int] = {}
    for task in tasks:
        if task.wbs_node_id is not None:
            counts[task.wbs_node_id] = counts.get(task.wbs_node_id, 0) + 1
    return counts


def _blocked_by(
    dependencies: list[TaskDependency],
    done_stage_ids: set[int],
    tasks: list[Task],
    project_key: str,
) -> dict[int, list[str]]:
    """Возвращает ключи незакрытых предшественников для каждой задачи."""
    tasks_by_id = {task.id: task for task in tasks}
    blocked: dict[int, list[str]] = {}
    for dependency in dependencies:
        predecessor = tasks_by_id.get(dependency.predecessor_task_id)
        if predecessor is None or predecessor.stage_id in done_stage_ids:
            continue
        key = build_task_key(project_key=project_key, number=predecessor.number)
        blocked.setdefault(dependency.successor_task_id, []).append(key)
    return blocked


def _cut(value: str, limit: int) -> str:
    """Обрезает текст по лимиту, помечая обрыв многоточием."""
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}…"


# Блок сверки ответа модели с реальными данными.


def _resolve_draft(
    draft: AnalyticsDraftSchema,
    slices: list[_ProjectSlice],
    today: date,
) -> dict[str, Any]:
    """Заменяет ключи из ответа модели проверенными ссылками на задачи.

    Ключ, которого нет в области анализа, молча отбрасывается: выдуманная
    ссылка хуже её отсутствия, потому что выглядит достоверно.
    """
    tasks_by_key: dict[str, AnalyticsTaskRefSchema] = {}
    project_names: dict[str, str] = {}
    for project_slice in slices:
        project_names[project_slice.project.key] = project_slice.project.name
        done_stage_ids = _done_stage_ids(project_slice.stages)
        for task in project_slice.tasks:
            key = build_task_key(project_key=project_slice.project.key, number=task.number)
            tasks_by_key[key] = AnalyticsTaskRefSchema(
                id=task.id,
                key=key,
                title=task.title,
                project_key=project_slice.project.key,
                due_date=task.due_date,
                is_overdue=is_task_overdue(
                    due_date=task.due_date,
                    is_done=task.stage_id in done_stage_ids,
                    today=today,
                ),
            )

    def refs(task_keys: list[str]) -> list[AnalyticsTaskRefSchema]:
        seen: set[str] = set()
        resolved = []
        for raw in task_keys:
            key = raw.strip().upper()
            if key in tasks_by_key and key not in seen:
                seen.add(key)
                resolved.append(tasks_by_key[key])
        return resolved

    def project_key(raw: str | None) -> str | None:
        return raw if raw in project_names else None

    findings = [
        AnalyticsFindingSchema(
            kind=item.kind,
            severity=item.severity,
            title=item.title,
            detail=item.detail,
            project_key=project_key(item.project_key),
            project_name=project_names.get(item.project_key or ""),
            tasks=refs(item.task_keys),
        )
        for item in draft.findings
    ]
    progress = [
        AnalyticsProgressSchema(
            title=item.title,
            detail=item.detail,
            project_key=project_key(item.project_key),
            project_name=project_names.get(item.project_key or ""),
            tasks=refs(item.task_keys),
        )
        for item in draft.progress
    ]
    recommendations = [
        AnalyticsRecommendationSchema(
            horizon=item.horizon,
            title=item.title,
            detail=item.detail,
            project_key=project_key(item.project_key),
            project_name=project_names.get(item.project_key or ""),
            tasks=refs(item.task_keys),
        )
        for item in draft.recommendations
    ]
    return {
        "headline": draft.headline,
        "health": draft.health.value,
        "health_note": draft.health_note,
        "findings": [item.model_dump(mode="json") for item in findings],
        "progress": [item.model_dump(mode="json") for item in progress],
        "recommendations": [item.model_dump(mode="json") for item in recommendations],
    }


def _to_report_schema(report: AnalyticsReport, project: Project | None) -> AnalyticsReportSchema:
    """Собирает публичный контракт свода из сохранённой записи.

    Проект передаётся отдельно, а не берётся из связи записи: ленивая загрузка
    в асинхронной сессии за пределами репозитория недопустима.
    """
    payload = report.payload or {}
    return AnalyticsReportSchema(
        id=report.id,
        scope=AnalyticsScope.PROJECT if report.project_id else AnalyticsScope.PORTFOLIO,
        project_id=report.project_id,
        project_key=project.key if project else None,
        project_name=project.name if project else None,
        created_at=report.created_at,
        created_by=report.created_by_display_name_snapshot,
        llm_model=report.llm_model,
        duration_ms=report.duration_ms,
        headline=payload.get("headline", ""),
        health=AnalyticsHealth(payload.get("health", AnalyticsHealth.WATCH.value)),
        health_note=payload.get("health_note", ""),
        findings=payload.get("findings", []),
        progress=payload.get("progress", []),
        recommendations=payload.get("recommendations", []),
        signals=payload.get("signals", {}),
        context=report.context_summary or {},
    )


def _display_name(user: User) -> str:
    """Фиксирует понятное имя автора запроса на момент формирования свода."""
    full_name = " ".join(
        part for part in (user.last_name, user.first_name, user.middle_name) if part
    )
    return (full_name or user.username)[:NAME_LIMIT]
