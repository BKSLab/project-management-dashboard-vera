from __future__ import annotations

import logging
from collections import Counter
from datetime import date

from pydantic import BaseModel, Field

from src.clients.qdrant import KnowledgeSearchHit
from src.core.settings import get_settings
from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexOperation,
    KnowledgeIndexStatus,
)
from src.db.models.projects import Project
from src.exceptions.base import RepositoryError
from src.exceptions.knowledge import (
    KnowledgeDisabledError,
    KnowledgeIndexJobsRepositoryError,
    KnowledgeProviderError,
    KnowledgeServiceError,
    ProjectAgentError,
)
from src.knowledge.documents import build_wbs_paths
from src.knowledge.runtime import KnowledgeRuntime, get_knowledge_runtime
from src.repositories.documents import DocumentsRepository
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.schemas.knowledge import (
    KnowledgeAnswerSchema,
    KnowledgeChatMessageSchema,
    KnowledgeSourceSchema,
    KnowledgeStatusSchema,
)
from src.services.prompts.project_agent import PROJECT_AGENT_SYSTEM_PROMPT
from src.services.tasks import build_task_key

logger = logging.getLogger(__name__)

class AgentOutput(BaseModel):
    """Внутренняя structured-схема ответа LLM."""

    answer: str = Field(min_length=1, max_length=20000)
    source_ids: list[str] = Field(default_factory=list, max_length=20)


class ProjectAgentService:
    """RAG-агент: semantic retrieval плюс обязательный актуальный SQL-срез."""

    def __init__(
        self,
        *,
        stages_repository: ProjectStagesRepository,
        tasks_repository: TasksRepository,
        wbs_nodes_repository: WbsNodesRepository,
        documents_repository: DocumentsRepository,
        activity_repository: TaskActivityRepository,
        jobs_repository: KnowledgeIndexJobsRepository,
        runtime: KnowledgeRuntime | None = None,
    ) -> None:
        self.stages_repository = stages_repository
        self.tasks_repository = tasks_repository
        self.wbs_nodes_repository = wbs_nodes_repository
        self.documents_repository = documents_repository
        self.activity_repository = activity_repository
        self.jobs_repository = jobs_repository
        self.runtime = runtime or get_knowledge_runtime()
        self.settings = get_settings()

    async def ask(
        self,
        *,
        project: Project,
        question: str,
        history: list[KnowledgeChatMessageSchema],
    ) -> KnowledgeAnswerSchema:
        """Формирует grounded-ответ внутри строго одной collection проекта."""
        try:
            stages = await self.stages_repository.get_by_project(project.id)
            tasks = await self.tasks_repository.get_by_project(project.id)
            nodes = await self.wbs_nodes_repository.get_by_project(project.id)
            documents = await self.documents_repository.get_by_project(project.id)
            activity = await self.activity_repository.get_recent_by_project(project.id, limit=30)
        except RepositoryError as error:
            raise ProjectAgentError(str(error)) from error

        semantic_hits: list[KnowledgeSearchHit] = []
        if self.settings.knowledge.knowledge_enabled:
            try:
                query_vector = await self.runtime.embedding_client.get_embedding(question.strip())
                semantic_hits = await self.runtime.qdrant_client.search(
                    project_id=project.id,
                    vector=query_vector,
                    limit=self.settings.knowledge.knowledge_agent_semantic_limit,
                    score_threshold=self.settings.knowledge.qdrant_score_threshold,
                )
            except KnowledgeProviderError:
                # Вопросы по текущим статусам продолжают работать по PostgreSQL даже
                # во время переиндексации или временной недоступности Qdrant/embeddings.
                logger.warning(
                    "⚠️ Semantic retrieval проекта id=%s недоступен; использую SQL-срез.",
                    project.id,
                    exc_info=True,
                )

        postgres_context, sources = self._build_postgres_context(
            project=project,
            stages=stages,
            tasks=tasks,
            nodes=nodes,
            documents=documents,
            activity=activity,
        )
        semantic_context = self._build_semantic_context(semantic_hits, sources)
        history_context = (
            "\n".join(f"{message.role.upper()}: {message.content}" for message in history[-10:])
            or "нет"
        )
        user_content = (
            f"Текущая дата: {date.today().isoformat()}\n\n"
            f"CURRENT_POSTGRES_STATE:\n{postgres_context}\n\n"
            f"SEMANTIC_CONTEXT:\n{semantic_context or 'релевантные фрагменты не найдены'}\n\n"
            f"DIALOG_HISTORY:\n{history_context}\n\n"
            f"QUESTION:\n{question.strip()}"
        )
        try:
            output = await self.runtime.llm_client.get_structured_response(
                system_prompt=PROJECT_AGENT_SYSTEM_PROMPT,
                content=user_content,
                schema=AgentOutput,
                max_completion_tokens=3000,
            )
        except KnowledgeProviderError:
            raise
        except Exception as error:
            raise ProjectAgentError(str(error)) from error

        selected: list[KnowledgeSourceSchema] = []
        seen: set[str] = set()
        for source_id in output.source_ids:
            source = sources.get(source_id)
            if source is not None and source_id not in seen:
                selected.append(source)
                seen.add(source_id)
        if not selected:
            for hit in semantic_hits[:5]:
                source_id = str(hit.payload.get("source_id") or "")
                source = sources.get(source_id)
                if source is not None and source_id not in seen:
                    selected.append(source)
                    seen.add(source_id)
        return KnowledgeAnswerSchema(answer=output.answer, sources=selected)

    async def get_status(self, project_id: int) -> KnowledgeStatusSchema:
        """Возвращает состояние очереди и доступность collection проекта."""
        try:
            counts = await self.jobs_repository.get_status_counts(project_id)
            last_error = await self.jobs_repository.get_last_error(project_id)
        except KnowledgeIndexJobsRepositoryError as error:
            raise KnowledgeServiceError(str(error)) from error

        points_count: int | None = None
        provider_error: str | None = None
        if self.settings.knowledge.knowledge_enabled:
            try:
                points_count = await self.runtime.qdrant_client.count(project_id)
            except KnowledgeProviderError as error:
                provider_error = error.error_details
        pending = counts.get(KnowledgeIndexStatus.PENDING, 0)
        processing = counts.get(KnowledgeIndexStatus.PROCESSING, 0)
        failed = counts.get(KnowledgeIndexStatus.FAILED, 0)
        return KnowledgeStatusSchema(
            enabled=self.settings.knowledge.knowledge_enabled,
            ready=(
                self.settings.knowledge.knowledge_enabled
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
        if not self.settings.knowledge.knowledge_enabled:
            raise KnowledgeDisabledError("KNOWLEDGE_ENABLED=false")
        try:
            await self.jobs_repository.enqueue(
                project_id=project_id,
                entity_type=KnowledgeEntityType.PROJECT,
                operation=KnowledgeIndexOperation.REINDEX_PROJECT,
            )
        except KnowledgeIndexJobsRepositoryError as error:
            raise KnowledgeServiceError(str(error)) from error

    def _build_postgres_context(
        self,
        *,
        project,
        stages,
        tasks,
        nodes,
        documents,
        activity,
    ) -> tuple[str, dict[str, KnowledgeSourceSchema]]:
        stage_by_id = {stage.id: stage for stage in stages}
        task_by_id = {task.id: task for task in tasks}
        wbs_paths = build_wbs_paths(nodes)
        counts = Counter(task.stage_id for task in tasks)
        sources: dict[str, KnowledgeSourceSchema] = {
            f"project:{project.id}": KnowledgeSourceSchema(
                source_id=f"project:{project.id}",
                entity_type="project",
                entity_id=project.id,
                title=f"{project.key} · {project.name}",
                excerpt=(project.description_md or "")[:500] or None,
            )
        }
        lines = [
            f"[project:{project.id}] Проект {project.key} · {project.name}",
            f"Статус: {project.status.value}; старт: {project.start_date or 'не указан'}; "
            f"срок проекта: {project.due_date or 'не указан'}",
            f"Описание: {project.description_md or 'не заполнено'}",
            "Стадии: "
            + "; ".join(
                f"{stage.name} — {counts.get(stage.id, 0)} задач"
                f"{' (завершающая)' if stage.is_done_stage else ''}"
                for stage in stages
            ),
            f"Всего задач: {len(tasks)}",
            "ЗАДАЧИ:",
        ]
        for task in tasks:
            stage = stage_by_id.get(task.stage_id)
            task_key = build_task_key(project.key, task.number)
            source_id = f"task:{task.id}"
            source = KnowledgeSourceSchema(
                source_id=source_id,
                entity_type="task",
                entity_id=task.id,
                task_id=task.id,
                title=f"{task_key} · {task.title}",
                excerpt=(task.description_md or "")[:500] or None,
            )
            sources[source_id] = source
            lines.append(
                f"[{source_id}] {task_key} | {task.title} | стадия={stage.name if stage else '?'} "
                f"| завершена={'да' if stage and stage.is_done_stage else 'нет'} "
                f"| приоритет={task.priority.value} | роль={task.role.value if task.role else '-'} "
                f"| исполнитель={task.assignee or '-'} | срок={task.due_date or '-'} "
                f"| ИСР={wbs_paths.get(task.wbs_node_id, '-') if task.wbs_node_id else '-'}"
            )

        lines.append("ДОКУМЕНТЫ:")
        for document in documents:
            source_id = f"document:{document.id}"
            sources[source_id] = KnowledgeSourceSchema(
                source_id=source_id,
                entity_type="document",
                entity_id=document.id,
                title=document.title,
                document_slug=document.slug,
                excerpt=document.content_md[:500] or None,
            )
            lines.append(f"[{source_id}] {document.title} | slug={document.slug}")

        if activity:
            lines.append("ПОСЛЕДНИЕ ИЗМЕНЕНИЯ:")
            for item in activity:
                task = task_by_id.get(item.task_id)
                if task is None:
                    continue
                task_key = build_task_key(project.key, task.number)
                lines.append(
                    f"[task:{task.id}] {item.created_at.isoformat()} {task_key}: "
                    f"{item.event_type.value}, {item.from_value or '-'} → {item.to_value or '-'}"
                )
        return "\n".join(lines), sources

    def _build_semantic_context(
        self,
        hits: list[KnowledgeSearchHit],
        sources: dict[str, KnowledgeSourceSchema],
    ) -> str:
        lines: list[str] = []
        best_by_source: set[str] = set()
        for hit in hits:
            payload = hit.payload
            source_id = str(payload.get("source_id") or "")
            entity_type = str(payload.get("entity_type") or "")
            try:
                entity_id = int(str(payload.get("entity_id")))
            except ValueError:
                continue
            if not source_id or entity_type not in {
                "project",
                "task",
                "document",
                "comment",
                "attachment",
            }:
                continue
            excerpt = str(payload.get("text") or "")[:1200]
            if source_id not in sources:
                task_id_value = payload.get("task_id")
                try:
                    task_id = int(str(task_id_value)) if task_id_value else None
                except ValueError:
                    task_id = None
                sources[source_id] = KnowledgeSourceSchema(
                    source_id=source_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    title=str(payload.get("title") or source_id),
                    excerpt=excerpt[:500] or None,
                    score=hit.score,
                    task_id=task_id,
                    document_slug=(
                        str(payload.get("document_slug")) if payload.get("document_slug") else None
                    ),
                )
            elif source_id not in best_by_source:
                current = sources[source_id]
                sources[source_id] = current.model_copy(
                    update={"score": hit.score, "excerpt": excerpt[:500] or current.excerpt}
                )
            best_by_source.add(source_id)
            lines.append(f"[{source_id}] score={hit.score:.3f}\n{excerpt}")
        return "\n\n".join(lines)
