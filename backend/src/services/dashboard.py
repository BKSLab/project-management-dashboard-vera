import logging
from datetime import date, timedelta

from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project, ProjectStatus
from src.db.models.tasks import Task
from src.exceptions.dashboard import DashboardServiceError
from src.exceptions.project_stages import ProjectStagesRepositoryError
from src.exceptions.projects import ProjectsRepositoryError
from src.exceptions.tasks import TasksRepositoryError
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.schemas.dashboard import (
    DashboardProjectSchema,
    DashboardSchema,
    DashboardTaskSchema,
    DashboardTotalsSchema,
)
from src.services.tasks import build_task_key
from src.utils.deadlines import DUE_SOON_DAYS, is_task_overdue

logger = logging.getLogger(__name__)

ATTENTION_TASKS_LIMIT = 8
RECENT_TASKS_LIMIT = 8

RepositoryErrors = (
    ProjectsRepositoryError,
    ProjectStagesRepositoryError,
    TasksRepositoryError,
)


class DashboardService:
    """Сервис сборки сводки по всем проектам."""

    def __init__(
        self,
        projects_repository: ProjectsRepository,
        members_repository: ProjectMembersRepository,
        stages_repository: ProjectStagesRepository,
        tasks_repository: TasksRepository,
    ):
        self.projects_repository = projects_repository
        self.members_repository = members_repository
        self.stages_repository = stages_repository
        self.tasks_repository = tasks_repository

    async def get_overview(self, user_id: int) -> DashboardSchema:
        """Собирает сводку по проектам пользователя.

        Показатели считаются агрегатными запросами по всему портфелю, поэтому
        количество проектов не влияет на число обращений к БД; отбор по
        доступности выполняется уже в памяти.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Сводка портфеля с карточками проектов и задачами, требующими внимания.

        Raises:
            DashboardServiceError: Если собрать сводку не удалось.
        """
        try:
            today = date.today()
            soon_until = today + timedelta(days=DUE_SOON_DAYS)

            allowed_ids = await self.members_repository.get_project_ids_for_user(user_id=user_id)
            projects = [
                project
                for project in await self.projects_repository.get_all()
                if project.id in allowed_ids
            ]
            stages = await self.stages_repository.get_all()
            counters = await self.tasks_repository.get_portfolio_counters(
                today=today,
                soon_until=soon_until,
            )
            stage_counts = await self.tasks_repository.get_stage_counts()
            attention_tasks = await self.tasks_repository.get_attention_tasks(
                today=today,
                soon_until=soon_until,
                limit=ATTENTION_TASKS_LIMIT,
                project_ids=allowed_ids,
            )
            recent_tasks = await self.tasks_repository.get_recent(
                limit=RECENT_TASKS_LIMIT,
                project_ids=allowed_ids,
            )

            projects_by_id = {project.id: project for project in projects}
            stages_by_id = {stage.id: stage for stage in stages}
            backlog_stage_ids = _collect_backlog_stage_ids(stages=stages)
            counters_by_project = {row.project_id: row for row in counters}
            backlog_by_project = _collect_backlog_counts(
                stage_counts=stage_counts,
                backlog_stage_ids=backlog_stage_ids,
            )

            project_cards = [
                _build_project_card(
                    project=project,
                    counters=counters_by_project.get(project.id),
                    backlog_tasks=backlog_by_project.get(project.id, 0),
                )
                for project in projects
            ]
            return DashboardSchema(
                totals=_build_totals(projects=projects, project_cards=project_cards),
                projects=project_cards,
                attention_tasks=[
                    _build_task_card(
                        task=task,
                        project=projects_by_id[task.project_id],
                        stage=stages_by_id[task.stage_id],
                        today=today,
                    )
                    for task in attention_tasks
                    if task.project_id in projects_by_id and task.stage_id in stages_by_id
                ],
                recent_tasks=[
                    _build_task_card(
                        task=task,
                        project=projects_by_id[task.project_id],
                        stage=stages_by_id[task.stage_id],
                        today=today,
                    )
                    for task in recent_tasks
                    if task.project_id in projects_by_id and task.stage_id in stages_by_id
                ],
            )
        except RepositoryErrors as error:
            logger.error("❌ Ошибка сборки сводки по проектам.", exc_info=True)
            raise DashboardServiceError(str(error)) from error


def _collect_backlog_stage_ids(stages: list[ProjectStage]) -> set[int]:
    """Возвращает идентификаторы первых стадий каждого проекта."""
    first_stage_by_project: dict[int, ProjectStage] = {}
    for stage in stages:
        current = first_stage_by_project.get(stage.project_id)
        if current is None or (stage.order_index, stage.id) < (current.order_index, current.id):
            first_stage_by_project[stage.project_id] = stage
    return {stage.id for stage in first_stage_by_project.values()}


def _collect_backlog_counts(stage_counts: list, backlog_stage_ids: set[int]) -> dict[int, int]:
    """Возвращает число задач в начальной стадии (бэклоге) каждого проекта."""
    counts: dict[int, int] = {}
    for row in stage_counts:
        if row.stage_id in backlog_stage_ids:
            counts[row.project_id] = counts.get(row.project_id, 0) + row.tasks_count
    return counts


def _build_project_card(
    project: Project,
    counters,
    backlog_tasks: int,
) -> DashboardProjectSchema:
    """Строит карточку проекта для дашборда."""
    total = int(getattr(counters, "total", 0) or 0)
    done = int(getattr(counters, "done", 0) or 0)
    overdue = int(getattr(counters, "overdue", 0) or 0)
    next_due_date = getattr(counters, "next_due_date", None)
    in_progress = max(total - done - backlog_tasks, 0)
    return DashboardProjectSchema(
        id=project.id,
        key=project.key,
        name=project.name,
        description_md=project.description_md,
        status=project.status,
        color=project.color,
        icon=project.icon,
        total_tasks=total,
        done_tasks=done,
        in_progress_tasks=in_progress,
        overdue_tasks=overdue,
        completion_rate=(done / total) if total else 0.0,
        next_due_date=next_due_date,
        updated_at=project.updated_at,
    )


def _build_totals(
    projects: list[Project],
    project_cards: list[DashboardProjectSchema],
) -> DashboardTotalsSchema:
    """Считает суммарные показатели портфеля."""
    total_tasks = sum(card.total_tasks for card in project_cards)
    done_tasks = sum(card.done_tasks for card in project_cards)
    return DashboardTotalsSchema(
        total_projects=len(projects),
        active_projects=sum(1 for project in projects if project.status == ProjectStatus.ACTIVE),
        total_tasks=total_tasks,
        done_tasks=done_tasks,
        in_progress_tasks=sum(card.in_progress_tasks for card in project_cards),
        overdue_tasks=sum(card.overdue_tasks for card in project_cards),
        completion_rate=(done_tasks / total_tasks) if total_tasks else 0.0,
    )


def _build_task_card(
    task: Task,
    project: Project,
    stage: ProjectStage,
    today: date,
) -> DashboardTaskSchema:
    """Строит карточку задачи для сводки дашборда."""
    return DashboardTaskSchema(
        id=task.id,
        key=build_task_key(project_key=project.key, number=task.number),
        title=task.title,
        project_id=project.id,
        project_key=project.key,
        project_name=project.name,
        project_color=project.color,
        stage_id=stage.id,
        stage_name=stage.name,
        priority=task.priority,
        due_date=task.due_date,
        is_overdue=is_task_overdue(
            due_date=task.due_date,
            is_done=stage.is_done_stage,
            today=today,
        ),
        updated_at=task.updated_at,
    )
