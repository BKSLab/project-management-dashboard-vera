from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from src.exceptions.documents import DocumentsRepositoryError
from src.exceptions.projects import ProjectNotFoundError, ProjectsRepositoryError
from src.exceptions.tasks import (
    TaskContextDocumentError,
    TaskContextFileError,
    TaskDescriptionRewriteError,
    TaskNotFoundError,
    TasksRepositoryError,
    TasksServiceError,
)
from src.knowledge.extract import INDEXABLE_EXTENSIONS, extract_indexable_text
from src.knowledge.runtime import KnowledgeRuntime, get_knowledge_runtime
from src.prompts.task_description import TASK_DESCRIPTION_REPHRASE_PROMPT
from src.repositories.documents import DocumentsRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.schemas.tasks import TaskRephraseRequestSchema, TaskRephraseResultSchema
from src.services.tasks import build_task_key

logger = logging.getLogger(__name__)

RELATED_TASKS_LIMIT = 12
PROJECT_DESCRIPTION_LIMIT = 3000
RELATED_TASK_DESCRIPTION_LIMIT = 900
DOCUMENT_CONTEXT_LIMIT = 5000
MAX_REPHRASE_FILES = 10


@dataclass(frozen=True, slots=True)
class TaskRephraseFile:
    """Прочитанный multipart-файл, ещё не сохранённый в задаче."""

    name: str
    content: bytes


class TaskDescriptionService:
    """Создаёт улучшенный черновик описания без изменения данных задачи."""

    def __init__(
        self,
        *,
        projects_repository: ProjectsRepository,
        tasks_repository: TasksRepository,
        documents_repository: DocumentsRepository,
        runtime: KnowledgeRuntime | None = None,
        file_context_limit: int = 5000,
    ) -> None:
        self.projects_repository = projects_repository
        self.tasks_repository = tasks_repository
        self.documents_repository = documents_repository
        self.runtime = runtime or get_knowledge_runtime()
        self.file_context_limit = file_context_limit

    async def rephrase(
        self,
        *,
        project_id: int,
        data: TaskRephraseRequestSchema,
        files: list[TaskRephraseFile],
    ) -> TaskRephraseResultSchema:
        """Возвращает новый текст, оставляя пользовательский черновик несохранённым."""
        try:
            project = await self.projects_repository.get_by_id(project_id=project_id)
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)

            current_task = None
            if data.task_id is not None:
                current_task = await self.tasks_repository.get_by_id(task_id=data.task_id)
                if current_task is None or current_task.project_id != project_id:
                    raise TaskNotFoundError(task_id=data.task_id)

            selected_documents = await self._get_documents(
                project_id=project_id,
                document_ids=data.document_ids,
            )
            extracted_files = await self._extract_files(files)
            related_tasks = await self.tasks_repository.get_by_project(project_id=project_id)
            related_tasks = [task for task in related_tasks if task.id != data.task_id]
            related_tasks.sort(key=lambda task: task.updated_at, reverse=True)

            payload = {
                "project": {
                    "key": project.key,
                    "name": project.name,
                    "description": _clip(project.description_md, PROJECT_DESCRIPTION_LIMIT),
                },
                "task": {
                    "key": (
                        build_task_key(project.key, current_task.number)
                        if current_task is not None
                        else None
                    ),
                    "title": data.title.strip(),
                    "draft_description": data.description_md.strip(),
                },
                "related_task_wording": [
                    {
                        "key": build_task_key(project.key, task.number),
                        "title": task.title,
                        "description": _clip(
                            task.description_md,
                            RELATED_TASK_DESCRIPTION_LIMIT,
                        ),
                    }
                    for task in related_tasks[:RELATED_TASKS_LIMIT]
                ],
                "selected_documents": [
                    {
                        "title": document.title,
                        "content": _clip(document.content_md, DOCUMENT_CONTEXT_LIMIT),
                    }
                    for document in selected_documents
                ],
                "new_files": extracted_files,
                "length_guidance": _length_guidance(data.description_md),
            }
            result = await self.runtime.llm_client.get_structured_response(
                system_prompt=TASK_DESCRIPTION_REPHRASE_PROMPT,
                content=json.dumps(payload, ensure_ascii=False),
                schema=TaskRephraseResultSchema,
                max_completion_tokens=1800,
            )
            description = result.description_md.strip()
            if not description or len(description) > _maximum_result_length(data.description_md):
                raise TaskDescriptionRewriteError(
                    "LLM вернула пустое или чрезмерно длинное описание."
                )
            return TaskRephraseResultSchema(description_md=description)
        except (
            ProjectNotFoundError,
            TaskNotFoundError,
            TaskContextDocumentError,
            TaskContextFileError,
            TaskDescriptionRewriteError,
        ):
            raise
        except (ProjectsRepositoryError, TasksRepositoryError, DocumentsRepositoryError) as error:
            logger.error(
                "❌ Не удалось собрать контекст задачи в проекте id=%s.",
                project_id,
                exc_info=True,
            )
            raise TasksServiceError(str(error)) from error

    async def _get_documents(self, *, project_id: int, document_ids: list[int]) -> list:
        unique_ids = list(dict.fromkeys(document_ids))
        documents = await self.documents_repository.get_by_ids(set(unique_ids))
        by_id = {document.id: document for document in documents}
        for document_id in unique_ids:
            document = by_id.get(document_id)
            if document is None or document.project_id != project_id:
                raise TaskContextDocumentError(document_id=document_id)
        return [by_id[document_id] for document_id in unique_ids]

    async def _extract_files(self, files: list[TaskRephraseFile]) -> list[dict[str, str]]:
        if len(files) > MAX_REPHRASE_FILES:
            raise TaskContextFileError(file_name=f"более {MAX_REPHRASE_FILES} файлов")
        result: list[dict[str, str]] = []
        for file in files:
            if Path(file.name).suffix.lower() not in INDEXABLE_EXTENSIONS:
                raise TaskContextFileError(file_name=file.name)
            try:
                extracted = await extract_indexable_text(
                    file.name,
                    file.content,
                    vision_client=self.runtime.vision_client,
                    max_chars=self.file_context_limit,
                )
            except ValueError as error:
                raise TaskContextFileError(file_name=file.name) from error
            if not extracted:
                raise TaskContextFileError(file_name=file.name)
            result.append({"name": file.name, "content": extracted})
        return result


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if len(normalized) <= limit else f"{normalized[:limit].rstrip()}…"


def _maximum_result_length(source: str) -> int:
    """Не даёт модели превратить короткий черновик в длинную спецификацию."""
    return min(12_000, max(600, int(len(source.strip()) * 1.8)))


def _length_guidance(source: str) -> str:
    maximum = _maximum_result_length(source)
    return f"Не более {maximum} символов; предпочтительно близко к длине исходного текста."
