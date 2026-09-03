from __future__ import annotations

import logging
from pathlib import Path

from src.core.settings import get_settings
from src.exceptions.documents import DocumentsServiceError
from src.exceptions.task_attachments import (
    TaskAttachmentsServiceError,
    TaskAttachmentTooLargeError,
    TaskAttachmentValidationError,
    TaskDocumentImportError,
)
from src.exceptions.tasks import TaskNotFoundError
from src.knowledge.extract import INDEXABLE_EXTENSIONS, extract_indexable_text
from src.knowledge.runtime import KnowledgeRuntime, get_knowledge_runtime
from src.repositories.tasks import TasksRepository
from src.schemas.task_documents import TaskDocumentImportSchema
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.task_attachments import TaskAttachmentsService

logger = logging.getLogger(__name__)


class TaskDocumentImportService:
    """Импортирует файл как оригинал задачи и текстовый документ проекта."""

    def __init__(
        self,
        *,
        tasks_repository: TasksRepository,
        attachments_service: TaskAttachmentsService,
        documents_service: DocumentsService,
        links_service: DocumentLinksService,
        runtime: KnowledgeRuntime | None = None,
    ) -> None:
        self.tasks_repository = tasks_repository
        self.attachments_service = attachments_service
        self.documents_service = documents_service
        self.links_service = links_service
        self.runtime = runtime or get_knowledge_runtime()
        self.settings = get_settings()

    @property
    def max_file_size(self) -> int:
        return self.attachments_service.max_file_size

    async def import_file(
        self,
        *,
        task_id: int,
        user_id: int,
        file_name: str,
        content_type: str | None,
        content: bytes,
    ) -> TaskDocumentImportSchema:
        """Сохраняет исходник, извлекает текст и создаёт связь документа с задачей."""
        task = await self.tasks_repository.get_by_id(task_id=task_id)
        if task is None:
            raise TaskNotFoundError(task_id=task_id)

        safe_name = Path((file_name or "").replace("\\", "/")).name.strip()
        if not content:
            raise TaskAttachmentValidationError("Нельзя загрузить пустой файл.")
        if len(content) > self.max_file_size:
            raise TaskAttachmentTooLargeError(max_size_mb=self.max_file_size // 1024 // 1024)
        if not safe_name or "\x00" in safe_name:
            raise TaskAttachmentValidationError("Имя файла некорректно.")
        if Path(safe_name).suffix.lower() not in INDEXABLE_EXTENSIONS:
            raise TaskDocumentImportError(
                "Этот формат нельзя преобразовать в документ проекта. "
                "Поддерживаются PDF, DOCX, TXT, Markdown, CSV, Excel и изображения."
            )
        try:
            extracted = await extract_indexable_text(
                safe_name,
                content,
                vision_client=self.runtime.vision_client,
                max_chars=self.settings.knowledge.knowledge_extract_max_chars,
            )
        except ValueError as error:
            raise TaskDocumentImportError(
                f"Не удалось прочитать «{safe_name}»: файл повреждён или имеет неверный формат."
            ) from error
        if not extracted:
            raise TaskDocumentImportError(
                f"В «{safe_name}» не удалось найти текст для документа проекта."
            )

        attachment = None
        document = None
        try:
            attachment = await self.attachments_service.upload_attachment(
                task_id=task_id,
                file_name=safe_name,
                content_type=content_type,
                content=content,
                index_for_knowledge=False,
            )
            title = safe_name[:255]
            document = await self.documents_service.create_document(
                project_id=task.project_id,
                title=title,
                slug=None,
                content_md=_document_markdown(title=title, content=extracted),
            )
            link = await self.links_service.create_link(
                document_id=document.id,
                task_id=task_id,
                user_id=user_id,
            )
            return TaskDocumentImportSchema(
                attachment=attachment,
                document=document,
                link=link,
            )
        except Exception:
            await self._compensate(
                task_id=task_id,
                attachment_id=attachment.id if attachment is not None else None,
                document_id=document.id if document is not None else None,
            )
            raise

    async def _compensate(
        self,
        *,
        task_id: int,
        attachment_id: int | None,
        document_id: int | None,
    ) -> None:
        """Удаляет промежуточные сущности, если составной импорт оборвался."""
        if document_id is not None:
            try:
                await self.documents_service.delete_document(document_id=document_id)
            except DocumentsServiceError:
                logger.warning(
                    "⚠️ Не удалось удалить промежуточный документ id=%s.",
                    document_id,
                    exc_info=True,
                )
        if attachment_id is not None:
            try:
                await self.attachments_service.delete_attachment(
                    task_id=task_id,
                    attachment_id=attachment_id,
                )
            except TaskAttachmentsServiceError:
                logger.warning(
                    "⚠️ Не удалось удалить промежуточный файл id=%s.",
                    attachment_id,
                    exc_info=True,
                )


def _document_markdown(*, title: str, content: str) -> str:
    normalized = content.strip()
    if Path(title).suffix.lower() == ".md":
        return normalized
    return f"# {title}\n\n{normalized}"
