from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.clients.embedding import EmbeddingClient
from src.clients.llm import LlmClient
from src.clients.qdrant import KnowledgeSearchHit, ProjectQdrantClient
from src.db.models.knowledge_index_jobs import (
    KnowledgeIndexStatus,
)
from src.db.models.projects import Project
from src.exceptions.base import RepositoryError
from src.exceptions.clients import ClientError
from src.exceptions.knowledge import (
    KnowledgeDisabledError,
    KnowledgeEventsServiceError,
    KnowledgeIndexJobsRepositoryError,
    KnowledgeProviderError,
    KnowledgeServiceError,
    ProjectAgentError,
)
from src.exceptions.projects import ProjectNotFoundError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.knowledge.documents import build_wbs_paths
from src.knowledge.retrieval import reciprocal_rank_fusion
from src.prompts.project_agent import (
    PROJECT_AGENT_SYSTEM_PROMPT,
    PROJECT_AGENT_TOOL_SELECTION_PROMPT,
)
from src.repositories.tasks import ProjectTaskStatistics
from src.schemas.knowledge import (
    KnowledgeAnswerSchema,
    KnowledgeChatMessageSchema,
    KnowledgeSourceSchema,
    KnowledgeStatusSchema,
)
from src.services.calendar import MAX_CALENDAR_RANGE_DAYS
from src.services.db_scope import ProjectAgentScope, ProjectAgentScopeFactory
from src.services.tasks import build_task_key

logger = logging.getLogger(__name__)

MAX_RETRIEVED_TASKS = 30
MAX_RETRIEVED_DOCUMENTS = 30
MAX_RETRIEVAL_CONTEXT = 30
MAX_TOOL_TASKS = 30
PROJECT_DESCRIPTION_LIMIT = 1200
TEXT_FRAGMENT_LIMIT = 1200
SOURCE_EXCERPT_LIMIT = 500


class StructuredToolName(StrEnum):
    """Разрешённые read-only инструменты Project Agent."""

    PROJECT_STATISTICS = "get_project_statistics"
    TASKS_BY_STATUS = "get_tasks_by_status"
    OVERDUE_TASKS = "get_overdue_tasks"
    PROJECT_STRUCTURE = "get_project_structure"
    RECENT_PROJECT_ACTIVITY = "get_recent_project_activity"
    CALENDAR = "get_calendar"
    UPCOMING_DEADLINES = "get_upcoming_deadlines"
    PROJECT_RISKS = "get_project_risks"
    MILESTONES = "get_milestones"
    SCHEDULE_DRIFT = "get_schedule_drift"
    PREVIEW_SCHEDULE_CHANGE = "preview_schedule_change"


class AgentToolCall(BaseModel):
    """Один выбранный моделью structured tool."""

    name: StructuredToolName
    stage_name: str | None = Field(default=None, max_length=255)
    date_from: date | None = None
    date_to: date | None = None
    task_key: str | None = Field(default=None, max_length=32)
    proposed_start_date: date | None = None
    proposed_due_date: date | None = None
    shift_days: int | None = Field(default=None, ge=-3650, le=3650)


class AgentToolPlan(BaseModel):
    """План SQL-инструментов и retrieval для текущего вопроса."""

    calls: list[AgentToolCall] = Field(default_factory=list, max_length=7)
    search_query: str | None = Field(default=None, max_length=2000)
    entity_type: (
        Literal["project", "task", "document", "comment", "attachment", "milestone"] | None
    ) = None


class AgentOutput(BaseModel):
    """Внутренняя structured-схема ответа LLM."""

    answer: str = Field(min_length=1, max_length=20000)
    source_ids: list[str] = Field(default_factory=list, max_length=20)


@dataclass(slots=True)
class _AgentDatabaseContext:
    """Данные PostgreSQL, загруженные ограниченными structured tools."""

    stages: list[Any]
    ranked_tasks: list[Any]
    ranked_documents: list[Any]
    nodes: list[Any]
    statistics: ProjectTaskStatistics | None = None
    tasks_by_status: list[tuple[str, Any | None, list[Any]]] = field(default_factory=list)
    overdue_tasks: list[Any] = field(default_factory=list)
    structure_counts: dict[int, int] | None = None
    activity: list[Any] = field(default_factory=list)
    activity_tasks: dict[int, Any] = field(default_factory=dict)
    calendar_results: dict[StructuredToolName, Any] = field(default_factory=dict)
    milestones: list[Any] = field(default_factory=list)
    scenario_preview: Any | None = None


class _SourceRegistry:
    """Связывает реальные source_id с непредсказуемыми хэндлами одного запроса."""

    def __init__(self) -> None:
        self.nonce = secrets.token_hex(8)
        self._by_handle: dict[str, KnowledgeSourceSchema] = {}
        self._handle_by_source_id: dict[str, str] = {}

    def register(self, source: KnowledgeSourceSchema) -> str:
        """Возвращает стабильный внутри запроса хэндл источника."""
        existing = self._handle_by_source_id.get(source.source_id)
        if existing is not None:
            return existing
        handle = f"SRC_{self.nonce}_{len(self._by_handle) + 1}"
        self._by_handle[handle] = source
        self._handle_by_source_id[source.source_id] = handle
        return handle

    def update(self, source_id: str, **changes: Any) -> KnowledgeSourceSchema | None:
        """Обновляет серверные метаданные уже зарегистрированного источника."""
        handle = self._handle_by_source_id.get(source_id)
        if handle is None:
            return None
        source = self._by_handle[handle].model_copy(update=changes)
        self._by_handle[handle] = source
        return source

    def resolve(self, handle: str) -> KnowledgeSourceSchema | None:
        """Разрешает только хэндл, выданный в текущем запросе."""
        return self._by_handle.get(handle)

    def get_handle(self, source_id: str) -> str | None:
        """Возвращает выданный хэндл по внутреннему source_id."""
        return self._handle_by_source_id.get(source_id)


@dataclass(frozen=True, slots=True)
class ProjectAgentConfig:
    """Настройки семантического поиска, нужные Project Agent.

    Сервис получает только те значения, которые действительно использует,
    а не весь объект настроек приложения.
    """

    knowledge_enabled: bool
    semantic_limit: int
    score_threshold: float


class ProjectAgentService:
    """RAG-агент: semantic retrieval плюс обязательный актуальный SQL-срез."""

    def __init__(
        self,
        *,
        scope: ProjectAgentScopeFactory,
        llm_client: LlmClient,
        embedding_client: EmbeddingClient,
        qdrant_client: ProjectQdrantClient,
        config: ProjectAgentConfig,
    ) -> None:
        """Создаёт Project Agent.

        Args:
            scope: Фабрика короткой области работы с базой. Между сбором
                данных и ответом модели соединение удерживаться не должно.
            llm_client: Клиент chat completions.
            embedding_client: Клиент API эмбеддингов.
            qdrant_client: Клиент векторного индекса.
            config: Настройки семантического поиска.
        """
        self.scope = scope
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.qdrant_client = qdrant_client
        self.config = config

    async def ask(
        self,
        *,
        project_id: int,
        question: str,
        history: list[KnowledgeChatMessageSchema],
    ) -> KnowledgeAnswerSchema:
        """Формирует grounded-ответ внутри строго одной collection проекта.

        Сценарий разделён на фазы: короткое чтение базы, затем внешние
        вызовы уже без открытого соединения.

        Args:
            project_id: Проект, в границах которого работает агент.
            question: Вопрос пользователя.
            history: Предыдущие сообщения диалога.

        Returns:
            Ответ агента вместе со списком источников.

        Raises:
            ProjectNotFoundError: Если проект не найден.
            KnowledgeProviderError: Если внешний сервис недоступен.
            ProjectAgentError: Если ответ не удалось сформировать.
        """
        ask_started_at = perf_counter()
        phases_ms: dict[str, float | None] = {
            "planner": None,
            "ranked_fts": None,
            "embedding": None,
            "qdrant": None,
            "llm": None,
        }
        normalized_question = question.strip()
        async with self.scope() as db:
            project = await self._require_project(db, project_id=project_id)
        phase_started_at = perf_counter()
        try:
            try:
                tool_plan = await self._select_tools(question=normalized_question, history=history)
            except KnowledgeProviderError:
                logger.warning(
                    "⚠️ Планировщик Project Agent недоступен для проекта id=%s; "
                    "использую базовый SQL-план.",
                    project.id,
                    exc_info=True,
                )
                tool_plan = AgentToolPlan(
                    calls=[AgentToolCall(name=StructuredToolName.PROJECT_STATISTICS)],
                    search_query=normalized_question,
                )
        finally:
            phases_ms["planner"] = self._elapsed_ms(phase_started_at)
        condensed_query = (tool_plan.search_query or "").strip()
        retrieval_query = condensed_query or normalized_question
        entity_type = tool_plan.entity_type
        # Короткая DB-фаза: собирается весь срез, нужный для ответа, и
        # соединение возвращается в пул до обращения к эмбеддингам,
        # Qdrant и модели.
        try:
            async with self.scope() as db:
                stages = await db.stages.get_by_project(project.id)
                phase_started_at = perf_counter()
                try:
                    ranked_tasks = (
                        await db.tasks.search_ranked(
                            project_id=project.id,
                            search=retrieval_query,
                            limit=MAX_RETRIEVED_TASKS,
                        )
                        if entity_type in (None, "task")
                        else []
                    )
                    ranked_documents = (
                        await db.documents.search_ranked(
                            project_id=project.id,
                            search=retrieval_query,
                            limit=MAX_RETRIEVED_DOCUMENTS,
                        )
                        if entity_type in (None, "document")
                        else []
                    )
                finally:
                    phases_ms["ranked_fts"] = self._elapsed_ms(phase_started_at)
                nodes = await db.wbs_nodes.get_by_project(project.id)
                database_context = await self._load_structured_tools(
                    db,
                    project=project,
                    stages=stages,
                    ranked_tasks=ranked_tasks,
                    ranked_documents=ranked_documents,
                    nodes=nodes,
                    tool_plan=tool_plan,
                )
        except RepositoryError as error:
            raise ProjectAgentError(str(error)) from error

        semantic_hits: list[KnowledgeSearchHit] = []
        if self.config.knowledge_enabled:
            try:
                phase_started_at = perf_counter()
                try:
                    query_vector = await self.embedding_client.get_embedding(
                        retrieval_query
                    )
                finally:
                    phases_ms["embedding"] = self._elapsed_ms(phase_started_at)
                phase_started_at = perf_counter()
                try:
                    semantic_hits = await self.qdrant_client.search(
                        project_id=project.id,
                        vector=query_vector,
                        limit=self.config.semantic_limit,
                        score_threshold=self.config.score_threshold,
                        entity_type=entity_type,
                    )
                finally:
                    phases_ms["qdrant"] = self._elapsed_ms(phase_started_at)
            except ClientError:
                # Вопросы по текущим статусам продолжают работать по PostgreSQL даже
                # во время переиндексации или временной недоступности Qdrant/embeddings.
                logger.warning(
                    "⚠️ Semantic retrieval проекта id=%s недоступен; использую SQL-срез.",
                    project.id,
                    exc_info=True,
                )

        registry = _SourceRegistry()
        postgres_context = self._build_postgres_context(
            project=project,
            context=database_context,
            registry=registry,
        )
        task_candidates = postgres_context.pop("retrieved_tasks")
        document_candidates = postgres_context.pop("retrieved_documents")
        semantic_candidates = self._build_semantic_context(semantic_hits, registry)
        retrieval_context = self._build_hybrid_context(
            task_candidates=task_candidates,
            document_candidates=document_candidates,
            semantic_candidates=semantic_candidates,
            registry=registry,
        )
        user_content = json.dumps(
            {
                "current_date": date.today().isoformat(),
                "current_postgres_state": postgres_context,
                "retrieval_context": retrieval_context,
                "dialog_history": [
                    {"role": message.role, "content": message.content[:TEXT_FRAGMENT_LIMIT]}
                    for message in history[-10:]
                ],
                "question": normalized_question,
                "retrieval_query": retrieval_query,
            },
            ensure_ascii=False,
        )
        phase_started_at = perf_counter()
        try:
            try:
                output = await self.llm_client.get_structured_response(
                    system_prompt=PROJECT_AGENT_SYSTEM_PROMPT,
                    content=user_content,
                    schema=AgentOutput,
                    max_completion_tokens=3000,
                )
            except ClientError as error:
                raise KnowledgeProviderError(str(error)) from error
            except Exception as error:
                raise ProjectAgentError(str(error)) from error

            selected: list[KnowledgeSourceSchema] = []
            seen: set[str] = set()
            for handle in output.source_ids:
                source = registry.resolve(handle)
                if source is not None and source.source_id not in seen:
                    selected.append(source)
                    seen.add(source.source_id)
            return KnowledgeAnswerSchema(answer=output.answer, sources=selected)
        finally:
            phases_ms["llm"] = self._elapsed_ms(phase_started_at)
            logger.info(
                "🤖 Метрики Project Agent: %s",
                json.dumps(
                    {
                        "event": "project_agent.ask",
                        "project_id": project.id,
                        "phases_ms": phases_ms,
                        "total_ms": self._elapsed_ms(ask_started_at),
                        "context_chars": len(user_content),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        """Возвращает длительность фазы по monotonic clock в миллисекундах."""
        return round((perf_counter() - started_at) * 1000, 3)

    @staticmethod
    async def _require_project(db: ProjectAgentScope, *, project_id: int) -> Project:
        """Возвращает проект области анализа или поднимает доменную ошибку."""
        project = await db.projects.get_by_id(project_id=project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)
        return project

    async def get_status(self, project_id: int) -> KnowledgeStatusSchema:
        """Возвращает состояние очереди и доступность collection проекта."""
        try:
            async with self.scope() as db:
                counts = await db.jobs.get_status_counts(project_id)
                last_error = await db.jobs.get_last_error(project_id)
        except KnowledgeIndexJobsRepositoryError as error:
            raise KnowledgeServiceError(str(error)) from error

        points_count: int | None = None
        provider_error: str | None = None
        if self.config.knowledge_enabled:
            try:
                points_count = await self.qdrant_client.count(project_id)
            except ClientError as error:
                provider_error = error.error_details
        pending = counts.get(KnowledgeIndexStatus.PENDING, 0)
        processing = counts.get(KnowledgeIndexStatus.PROCESSING, 0)
        failed = counts.get(KnowledgeIndexStatus.FAILED, 0)
        return KnowledgeStatusSchema(
            enabled=self.config.knowledge_enabled,
            ready=(
                self.config.knowledge_enabled
                and points_count is not None
                and pending == 0
                and processing == 0
            ),
            points_count=points_count,
            pending_jobs=pending,
            processing_jobs=processing,
            failed_jobs=failed,
            last_error=provider_error or last_error,
        )

    async def reindex(self, project_id: int) -> None:
        """Ставит ручную полную пересборку в постоянную очередь."""
        if not self.config.knowledge_enabled:
            raise KnowledgeDisabledError("KNOWLEDGE_ENABLED=false")
        try:
            # Постановка задания и её фиксация — один факт: владелец
            # транзакции здесь, а не внутри репозитория очереди.
            async with self.scope() as db:
                await db.knowledge_events.reindex_project(project_id=project_id)
                await db.unit_of_work.commit()
        except (KnowledgeEventsServiceError, UnitOfWorkRepositoryError) as error:
            raise KnowledgeServiceError(str(error)) from error

    async def _select_tools(
        self,
        *,
        question: str,
        history: list[KnowledgeChatMessageSchema],
    ) -> AgentToolPlan:
        """Просит модель выбрать только необходимые structured tools."""
        content = json.dumps(
            {
                "question": question,
                "history": [
                    {"role": message.role, "content": message.content[:TEXT_FRAGMENT_LIMIT]}
                    for message in history[-10:]
                ],
            },
            ensure_ascii=False,
        )
        try:
            return await self.llm_client.get_structured_response(
                system_prompt=PROJECT_AGENT_TOOL_SELECTION_PROMPT,
                content=content,
                schema=AgentToolPlan,
                max_completion_tokens=700,
            )
        except ClientError as error:
            raise KnowledgeProviderError(str(error)) from error
        except Exception as error:
            raise ProjectAgentError(str(error)) from error

    async def _load_structured_tools(
        self,
        db: ProjectAgentScope,
        *,
        project: Project,
        stages: list[Any],
        ranked_tasks: list[Any],
        ranked_documents: list[Any],
        nodes: list[Any],
        tool_plan: AgentToolPlan,
    ) -> _AgentDatabaseContext:
        """Выполняет выбранные моделью ограниченные запросы PostgreSQL."""
        context = _AgentDatabaseContext(
            stages=stages,
            ranked_tasks=ranked_tasks,
            ranked_documents=ranked_documents,
            nodes=nodes,
        )
        stages_by_name = {stage.name.casefold(): stage for stage in stages}
        project_id = project.id
        current_date = date.today()
        seen: set[tuple[Any, ...]] = set()
        for tool_call in tool_plan.calls:
            normalized_stage = tool_call.stage_name.strip() if tool_call.stage_name else None
            key = (
                tool_call.name,
                normalized_stage.casefold() if normalized_stage is not None else None,
                tool_call.date_from,
                tool_call.date_to,
                tool_call.task_key,
                tool_call.proposed_start_date,
                tool_call.proposed_due_date,
                tool_call.shift_days,
            )
            if key in seen:
                continue
            seen.add(key)
            if tool_call.name is StructuredToolName.PROJECT_STATISTICS:
                context.statistics = await db.tasks.get_project_statistics(
                    project_id=project_id,
                    today=current_date,
                )
            elif tool_call.name is StructuredToolName.TASKS_BY_STATUS:
                stage = (
                    stages_by_name.get(normalized_stage.casefold()) if normalized_stage else None
                )
                tasks = (
                    await db.tasks.get_by_stage_limited(
                        project_id=project_id,
                        stage_id=stage.id,
                        limit=MAX_TOOL_TASKS,
                    )
                    if stage is not None
                    else []
                )
                context.tasks_by_status.append((normalized_stage or "", stage, tasks))
            elif tool_call.name is StructuredToolName.OVERDUE_TASKS:
                context.overdue_tasks = await db.tasks.get_overdue_limited(
                    project_id=project_id,
                    today=current_date,
                    limit=MAX_TOOL_TASKS,
                )
            elif tool_call.name is StructuredToolName.PROJECT_STRUCTURE:
                context.structure_counts = await db.tasks.get_wbs_counts(project_id)
            elif tool_call.name is StructuredToolName.RECENT_PROJECT_ACTIVITY:
                context.activity = await db.activity.get_recent_by_project(
                    project_id,
                    limit=30,
                )
                activity_tasks = await db.tasks.get_by_ids(
                    {item.task_id for item in context.activity}
                )
                context.activity_tasks = {task.id: task for task in activity_tasks}
            elif (
                tool_call.name
                in {
                    StructuredToolName.CALENDAR,
                    StructuredToolName.UPCOMING_DEADLINES,
                    StructuredToolName.PROJECT_RISKS,
                    StructuredToolName.SCHEDULE_DRIFT,
                }
            ):
                date_from, date_to = _agent_calendar_range(
                    tool_call=tool_call,
                    project=project,
                    current_date=current_date,
                )
                context.calendar_results[tool_call.name] = await db.calendar.get_range(
                    project_id=project_id,
                    date_from=date_from,
                    date_to=date_to,
                    today=current_date,
                )
            elif tool_call.name is StructuredToolName.MILESTONES:
                context.milestones = (await db.milestones.get_by_project(project_id))[
                    :MAX_TOOL_TASKS
                ]
            elif tool_call.name is StructuredToolName.PREVIEW_SCHEDULE_CHANGE:
                task_number = _task_number(tool_call.task_key, project.key)
                if task_number is None:
                    context.scenario_preview = {
                        "error": "Для preview нужен ключ задачи текущего проекта."
                    }
                    continue
                task = await db.tasks.get_by_project_number(
                    project_id,
                    task_number,
                )
                if task is None:
                    context.scenario_preview = {"error": "Задача для preview не найдена."}
                    continue
                start_date, due_date = _proposed_tool_dates(task, tool_call)
                if start_date == task.start_date and due_date == task.due_date:
                    context.scenario_preview = {"error": "Для preview не передано изменение дат."}
                    continue
                context.scenario_preview = await db.scenario.preview(
                    project_id,
                    [
                        {
                            "task_id": task.id,
                            "start_date": start_date,
                            "due_date": due_date,
                        }
                    ],
                )
        return context

    def _build_postgres_context(
        self,
        *,
        project: Project,
        context: _AgentDatabaseContext,
        registry: _SourceRegistry,
    ) -> dict[str, Any]:
        """Собирает ограниченный JSON-совместимый срез актуальных данных."""
        stage_by_id = {stage.id: stage for stage in context.stages}
        wbs_paths = build_wbs_paths(context.nodes)
        project_source = KnowledgeSourceSchema(
            source_id=f"project:{project.id}",
            entity_type="project",
            entity_id=project.id,
            title=f"{project.key} · {project.name}"[:512],
            excerpt=(project.description_md or "")[:SOURCE_EXCERPT_LIMIT] or None,
        )
        result: dict[str, Any] = {
            "project": {
                "source_handle": registry.register(project_source),
                "key": project.key,
                "name": project.name[:512],
                "status": getattr(project.status, "value", str(project.status)),
                "start_date": str(project.start_date) if project.start_date else None,
                "due_date": str(project.due_date) if project.due_date else None,
                "description": (project.description_md or "")[:PROJECT_DESCRIPTION_LIMIT],
            },
            "stages": [
                {
                    "name": stage.name[:255],
                    "is_done_stage": stage.is_done_stage,
                }
                for stage in context.stages
            ],
            "retrieved_tasks": [
                self._task_context(
                    task=task,
                    project=project,
                    stage_by_id=stage_by_id,
                    wbs_paths=wbs_paths,
                    registry=registry,
                )
                for task in context.ranked_tasks[:MAX_RETRIEVED_TASKS]
            ],
            "retrieved_documents": [
                self._document_context(document=document, registry=registry)
                for document in context.ranked_documents[:MAX_RETRIEVED_DOCUMENTS]
            ],
            "tool_results": {},
        }
        tools: dict[str, Any] = result["tool_results"]
        if context.statistics is not None:
            statistics = context.statistics
            tools[StructuredToolName.PROJECT_STATISTICS.value] = {
                "total": statistics.total,
                "overdue": statistics.overdue,
                "by_stage": {
                    stage_by_id[stage_id].name: count
                    for stage_id, count in statistics.by_stage.items()
                    if stage_id in stage_by_id
                },
                "by_priority": statistics.by_priority,
                "by_assignee": statistics.by_assignee,
            }
        if context.tasks_by_status:
            tools[StructuredToolName.TASKS_BY_STATUS.value] = [
                {
                    "requested_stage": requested_stage,
                    "matched_stage": stage.name if stage is not None else None,
                    "tasks": [
                        self._task_context(
                            task=task,
                            project=project,
                            stage_by_id=stage_by_id,
                            wbs_paths=wbs_paths,
                            registry=registry,
                        )
                        for task in tasks[:MAX_TOOL_TASKS]
                    ],
                }
                for requested_stage, stage, tasks in context.tasks_by_status
            ]
        if context.overdue_tasks:
            tools[StructuredToolName.OVERDUE_TASKS.value] = [
                self._task_context(
                    task=task,
                    project=project,
                    stage_by_id=stage_by_id,
                    wbs_paths=wbs_paths,
                    registry=registry,
                )
                for task in context.overdue_tasks[:MAX_TOOL_TASKS]
            ]
        if context.structure_counts is not None:
            tools[StructuredToolName.PROJECT_STRUCTURE.value] = [
                {
                    "path": wbs_paths.get(node.id, node.title)[:TEXT_FRAGMENT_LIMIT],
                    "tasks_count": context.structure_counts.get(node.id, 0),
                }
                for node in context.nodes
            ]
        if context.activity:
            activity_rows: list[dict[str, Any]] = []
            for item in context.activity[:30]:
                task = context.activity_tasks.get(item.task_id)
                if task is None:
                    continue
                activity_rows.append(
                    {
                        "source_handle": registry.register(self._task_source(task, project)),
                        "task_key": build_task_key(project.key, task.number),
                        "created_at": item.created_at.isoformat(),
                        "event_type": item.event_type.value,
                        "from_value": item.from_value,
                        "to_value": item.to_value,
                    }
                )
            tools[StructuredToolName.RECENT_PROJECT_ACTIVITY.value] = activity_rows
        for tool_name, calendar in context.calendar_results.items():
            tools[tool_name.value] = self._calendar_tool_context(
                tool_name=tool_name,
                calendar=calendar,
                registry=registry,
            )
        if context.milestones:
            tools[StructuredToolName.MILESTONES.value] = [
                self._milestone_context(milestone, registry)
                for milestone in context.milestones[:MAX_TOOL_TASKS]
            ]
        if context.scenario_preview is not None:
            tools[StructuredToolName.PREVIEW_SCHEDULE_CHANGE.value] = (
                self._scenario_context(context.scenario_preview, registry)
                if not isinstance(context.scenario_preview, dict)
                else context.scenario_preview
            )
        return result

    def _calendar_tool_context(
        self,
        *,
        tool_name: StructuredToolName,
        calendar: Any,
        registry: _SourceRegistry,
    ) -> dict[str, Any]:
        """Сериализует результат детерминированного CalendarService."""
        tasks = calendar.tasks
        if tool_name is StructuredToolName.PROJECT_RISKS:
            tasks = [task for task in tasks if task.risk_reasons]
        elif tool_name is StructuredToolName.SCHEDULE_DRIFT:
            tasks = [task for task in tasks if task.drift_days not in {None, 0}]
        return {
            "range": calendar.range.model_dump(mode="json"),
            "summary": calendar.summary.model_dump(mode="json"),
            "tasks": [
                {
                    "source_handle": registry.register(
                        KnowledgeSourceSchema(
                            source_id=f"task:{task.id}",
                            entity_type="task",
                            entity_id=task.id,
                            task_id=task.id,
                            title=f"{task.key} · {task.title}"[:512],
                        )
                    ),
                    "task_key": task.key,
                    "title": task.title[:512],
                    "start_date": str(task.start_date) if task.start_date else None,
                    "due_date": str(task.due_date) if task.due_date else None,
                    "baseline_start_date": (
                        str(task.baseline_start_date) if task.baseline_start_date else None
                    ),
                    "baseline_due_date": (
                        str(task.baseline_due_date) if task.baseline_due_date else None
                    ),
                    "drift_days": task.drift_days,
                    "assignee": task.assignee,
                    "is_done": task.is_done,
                    "risk_level": task.risk_level,
                    "risk_reasons": [
                        reason.model_dump(mode="json", exclude_none=True)
                        for reason in task.risk_reasons
                    ],
                }
                for task in tasks[:MAX_TOOL_TASKS]
            ],
            "milestones": [
                self._calendar_milestone_context(milestone, registry)
                for milestone in calendar.milestones[:MAX_TOOL_TASKS]
            ],
        }

    @staticmethod
    def _calendar_milestone_context(
        milestone: Any,
        registry: _SourceRegistry,
    ) -> dict[str, Any]:
        result = {
            "title": milestone.title[:512],
            "due_date": str(milestone.due_date),
            "status": milestone.status.value,
            "is_system": milestone.is_system,
        }
        if milestone.id is not None:
            result["source_handle"] = registry.register(
                KnowledgeSourceSchema(
                    source_id=f"milestone:{milestone.id}",
                    entity_type="milestone",
                    entity_id=milestone.id,
                    title=milestone.title[:512],
                    excerpt=(milestone.description_md or "")[:SOURCE_EXCERPT_LIMIT] or None,
                )
            )
        return result

    @staticmethod
    def _milestone_context(milestone: Any, registry: _SourceRegistry) -> dict[str, Any]:
        source = KnowledgeSourceSchema(
            source_id=f"milestone:{milestone.id}",
            entity_type="milestone",
            entity_id=milestone.id,
            title=milestone.title[:512],
            excerpt=(milestone.description_md or "")[:SOURCE_EXCERPT_LIMIT] or None,
        )
        return {
            "source_handle": registry.register(source),
            "title": milestone.title[:512],
            "description": (milestone.description_md or "")[:TEXT_FRAGMENT_LIMIT],
            "due_date": str(milestone.due_date),
            "status": milestone.status.value,
        }

    @staticmethod
    def _scenario_context(preview: Any, registry: _SourceRegistry) -> dict[str, Any]:
        return {
            "can_apply": preview.can_apply,
            "consequences_count": preview.consequences_count,
            "conflicts": [item.model_dump(mode="json") for item in preview.conflicts],
            "changes": [
                {
                    "source_handle": registry.register(
                        KnowledgeSourceSchema(
                            source_id=f"task:{change.task_id}",
                            entity_type="task",
                            entity_id=change.task_id,
                            task_id=change.task_id,
                            title=f"{change.task_key} · {change.task_title}"[:512],
                        )
                    ),
                    "task_key": change.task_key,
                    "title": change.task_title[:512],
                    "source": change.source.value,
                    "current": change.current.model_dump(mode="json"),
                    "proposed": change.proposed.model_dump(mode="json"),
                    "reasons": [
                        reason.model_dump(mode="json", exclude_none=True)
                        for reason in change.reasons
                    ],
                }
                for change in preview.changes[:MAX_TOOL_TASKS]
            ],
        }

    def _task_context(
        self,
        *,
        task: Any,
        project: Project,
        stage_by_id: dict[int, Any],
        wbs_paths: dict[int, str],
        registry: _SourceRegistry,
    ) -> dict[str, Any]:
        """Сериализует одну retrieved-задачу с ограниченными строками."""
        stage = stage_by_id.get(task.stage_id)
        return {
            "kind": "task",
            "source_handle": registry.register(self._task_source(task, project)),
            "task_key": build_task_key(project.key, task.number),
            "title": task.title[:512],
            "description": (task.description_md or "")[:TEXT_FRAGMENT_LIMIT],
            "stage": stage.name[:255] if stage is not None else None,
            "is_done": bool(stage and stage.is_done_stage),
            "priority": task.priority.value,
            "role": task.role.value if task.role else None,
            "assignee": task.assignee,
            "due_date": str(task.due_date) if task.due_date else None,
            "wbs_path": (
                wbs_paths.get(task.wbs_node_id, "")[:TEXT_FRAGMENT_LIMIT]
                if task.wbs_node_id
                else None
            ),
        }

    def _document_context(
        self,
        *,
        document: Any,
        registry: _SourceRegistry,
    ) -> dict[str, Any]:
        """Сериализует один найденный PostgreSQL-документ."""
        return {
            "kind": "document",
            "source_handle": registry.register(self._document_source(document)),
            "title": document.title[:512],
            "slug": document.slug[:255],
            "content": (document.content_md or "")[:TEXT_FRAGMENT_LIMIT],
        }

    @staticmethod
    def _task_source(task: Any, project: Project) -> KnowledgeSourceSchema:
        """Строит серверные метаданные источника задачи."""
        task_key = build_task_key(project.key, task.number)
        return KnowledgeSourceSchema(
            source_id=f"task:{task.id}",
            entity_type="task",
            entity_id=task.id,
            task_id=task.id,
            title=f"{task_key} · {task.title}"[:512],
            excerpt=(task.description_md or "")[:SOURCE_EXCERPT_LIMIT] or None,
        )

    @staticmethod
    def _document_source(document: Any) -> KnowledgeSourceSchema:
        """Строит серверные метаданные источника wiki-документа."""
        return KnowledgeSourceSchema(
            source_id=f"document:{document.id}",
            entity_type="document",
            entity_id=document.id,
            title=document.title[:512],
            excerpt=(document.content_md or "")[:SOURCE_EXCERPT_LIMIT] or None,
            document_slug=document.slug[:255],
        )

    def _build_semantic_context(
        self,
        hits: list[KnowledgeSearchHit],
        registry: _SourceRegistry,
    ) -> list[dict[str, Any]]:
        """Преобразует Qdrant hits в JSON с непредсказуемыми source handles."""
        result: list[dict[str, Any]] = []
        seen_sources: set[str] = set()
        for hit in hits:
            payload = hit.payload
            source_id = str(payload.get("source_id") or "")
            entity_type = str(payload.get("entity_type") or "")
            try:
                entity_id = int(str(payload.get("entity_id")))
            except ValueError:
                continue
            if entity_type not in {
                "project",
                "task",
                "document",
                "comment",
                "attachment",
                "milestone",
            }:
                continue
            if source_id != f"{entity_type}:{entity_id}":
                continue
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            excerpt = str(payload.get("text") or "")[:TEXT_FRAGMENT_LIMIT]
            source = registry.update(
                source_id,
                score=hit.score,
                excerpt=excerpt[:SOURCE_EXCERPT_LIMIT] or None,
            )
            if source is None:
                task_id_value = payload.get("task_id")
                try:
                    task_id = int(str(task_id_value)) if task_id_value else None
                except ValueError:
                    task_id = None
                source = KnowledgeSourceSchema(
                    source_id=source_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    title=str(payload.get("title") or source_id)[:512],
                    excerpt=excerpt[:SOURCE_EXCERPT_LIMIT] or None,
                    score=hit.score,
                    task_id=task_id,
                    document_slug=(
                        str(payload.get("document_slug"))[:255]
                        if payload.get("document_slug")
                        else None
                    ),
                )
            handle = registry.register(source)
            result.append(
                {
                    "kind": "semantic_fragment",
                    "source_handle": handle,
                    "score": round(hit.score, 6),
                    "text": excerpt,
                }
            )
        return result

    def _build_hybrid_context(
        self,
        *,
        task_candidates: list[dict[str, Any]],
        document_candidates: list[dict[str, Any]],
        semantic_candidates: list[dict[str, Any]],
        registry: _SourceRegistry,
    ) -> list[dict[str, Any]]:
        """Объединяет PostgreSQL FTS и Qdrant-кандидатов по RRF."""

        def source_ids(candidates: list[dict[str, Any]]) -> list[str]:
            result: list[str] = []
            for candidate in candidates:
                source = registry.resolve(candidate["source_handle"])
                if source is not None:
                    result.append(source.source_id)
            return result

        scores = reciprocal_rank_fusion(
            [
                source_ids(task_candidates),
                source_ids(document_candidates),
                source_ids(semantic_candidates),
            ]
        )
        lexical_by_source: dict[str, dict[str, Any]] = {}
        for candidate in [*task_candidates, *document_candidates]:
            source = registry.resolve(candidate["source_handle"])
            if source is not None:
                lexical_by_source.setdefault(source.source_id, candidate)
        semantic_by_source: dict[str, dict[str, Any]] = {}
        for candidate in semantic_candidates:
            source = registry.resolve(candidate["source_handle"])
            if source is not None:
                semantic_by_source.setdefault(source.source_id, candidate)

        result: list[dict[str, Any]] = []
        for source_id, score in scores.items():
            handle = registry.get_handle(source_id)
            source = registry.resolve(handle) if handle is not None else None
            if handle is None or source is None:
                continue
            lexical = lexical_by_source.get(source_id)
            semantic = semantic_by_source.get(source_id)
            result.append(
                {
                    "source_handle": handle,
                    "entity_type": source.entity_type,
                    "rrf_score": round(score, 8),
                    "current_data": lexical,
                    "semantic_fragment": semantic,
                }
            )
            if len(result) >= MAX_RETRIEVAL_CONTEXT:
                break
        return result


def _agent_calendar_range(
    *,
    tool_call: AgentToolCall,
    project: Project,
    current_date: date,
) -> tuple[date, date]:
    """Возвращает ограниченный диапазон для выбранного calendar tool."""
    if tool_call.name is StructuredToolName.UPCOMING_DEADLINES:
        return current_date, current_date + timedelta(days=30)
    if tool_call.name is StructuredToolName.PROJECT_RISKS:
        return current_date - timedelta(days=90), current_date + timedelta(days=90)
    if tool_call.name is StructuredToolName.SCHEDULE_DRIFT:
        date_from = project.start_date or current_date - timedelta(days=185)
        date_to = project.due_date or current_date + timedelta(days=185)
    else:
        date_from = tool_call.date_from or current_date - timedelta(days=30)
        date_to = tool_call.date_to or current_date + timedelta(days=60)
    if date_to < date_from:
        date_from = current_date - timedelta(days=30)
        date_to = current_date + timedelta(days=60)
    if (date_to - date_from).days > MAX_CALENDAR_RANGE_DAYS:
        date_to = date_from + timedelta(days=MAX_CALENDAR_RANGE_DAYS)
    return date_from, date_to


def _task_number(task_key: str | None, project_key: str) -> int | None:
    """Разбирает ключ задачи только текущего проекта."""
    if task_key is None:
        return None
    prefix, separator, number = task_key.strip().upper().rpartition("-")
    if separator != "-" or prefix != project_key.upper() or not number.isdigit():
        return None
    return int(number)


def _proposed_tool_dates(task: Any, tool_call: AgentToolCall) -> tuple[date | None, date | None]:
    """Применяет сдвиг и явные даты к текущему интервалу задачи."""
    start_date = task.start_date
    due_date = task.due_date
    if tool_call.shift_days is not None:
        delta = timedelta(days=tool_call.shift_days)
        start_date = start_date + delta if start_date is not None else None
        due_date = due_date + delta if due_date is not None else None
    if tool_call.proposed_start_date is not None:
        start_date = tool_call.proposed_start_date
    if tool_call.proposed_due_date is not None:
        due_date = tool_call.proposed_due_date
    return start_date, due_date
