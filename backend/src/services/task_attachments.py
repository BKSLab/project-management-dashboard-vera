from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from src.db.models.knowledge_index_jobs import KnowledgeEntityType
from src.db.models.task_attachments import TaskAttachment
from src.db.models.tasks import Task
from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.task_attachments import (
    TaskAttachmentLimitError,
    TaskAttachmentNotFoundError,
    TaskAttachmentsRepositoryError,
    TaskAttachmentsServiceError,
    TaskAttachmentStorageError,
    TaskAttachmentTooLargeError,
    TaskAttachmentUnsupportedTypeError,
    TaskAttachmentValidationError,
)
from src.exceptions.tasks import TaskNotFoundError, TasksRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.task_attachments import TaskAttachmentSchema
from src.services.knowledge_events import KnowledgeEvents
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TaskAttachmentContent:
    """Проверенный файл и HTTP-метаданные для выдачи клиенту."""

    path: Path
    original_name: str
    content_type: str
    previewable: bool


class TaskAttachmentsService:
    """Сервис сценариев работы с файлами задач."""

    MAX_FILE_SIZE = 10 * 1024 * 1024
    MAX_FILES_PER_TASK = 20
    ALLOWED_EXTENSIONS = frozenset(
        {
            ".7z",
            ".avif",
            ".bmp",
            ".csv",
            ".doc",
            ".docx",
            ".gif",
            ".gz",
            ".jpeg",
            ".jpg",
            ".log",
            ".md",
            ".odp",
            ".ods",
            ".odt",
            ".pdf",
            ".png",
            ".ppt",
            ".pptx",
            ".rar",
            ".rtf",
            ".tar",
            ".txt",
            ".webp",
            ".xls",
            ".xlsx",
            ".zip",
        }
    )
    PREVIEWABLE_EXTENSIONS = frozenset({".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"})

    def __init__(
        self,
        attachments_repository: TaskAttachmentsRepository,
        tasks_repository: TasksRepository,
        storage: TaskAttachmentStorage,
        unit_of_work: UnitOfWork,
        knowledge_events: KnowledgeEvents | None = None,
    ) -> None:
        self.attachments_repository = attachments_repository
        self.tasks_repository = tasks_repository
        self.storage = storage
        self.unit_of_work = unit_of_work
        self.knowledge_events = knowledge_events

    @property
    def max_file_size(self) -> int:
        """Возвращает максимальный размер чтения multipart-файла."""
        return self.MAX_FILE_SIZE

    async def get_attachments(self, task_id: int) -> list[TaskAttachmentSchema]:
        """Возвращает файлы существующей задачи.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            Метаданные файлов в хронологическом порядке.

        Raises:
            TaskNotFoundError: Если задача не найдена.
            TaskAttachmentsServiceError: Если получить файлы не удалось.
        """
        try:
            await self._ensure_task_exists(task_id)
            attachments = await self.attachments_repository.get_for_task(task_id=task_id)
            return [self._to_schema(attachment) for attachment in attachments]
        except TaskNotFoundError:
            raise
        except (TaskAttachmentsRepositoryError, TasksRepositoryError) as error:
            logger.error("❌ Ошибка получения файлов задачи id=%s.", task_id, exc_info=True)
            raise TaskAttachmentsServiceError(str(error)) from error

    async def upload_attachment(
        self,
        *,
        task_id: int,
        file_name: str,
        content_type: str | None,
        content: bytes,
        index_for_knowledge: bool = True,
    ) -> TaskAttachmentSchema:
        """Проверяет и сохраняет новый файл задачи.

        Args:
            task_id: Идентификатор задачи.
            file_name: Исходное имя из multipart-запроса.
            content_type: MIME-тип, заявленный клиентом.
            content: Прочитанное с ограничением бинарное содержимое.

        Returns:
            Метаданные созданного файла.

        Raises:
            TaskNotFoundError: Если задача не найдена.
            TaskAttachmentValidationError: Если файл пуст или имя некорректно.
            TaskAttachmentTooLargeError: Если файл превышает 10 МБ.
            TaskAttachmentUnsupportedTypeError: Если расширение запрещено.
            TaskAttachmentLimitError: Если к задаче уже прикреплено 20 файлов.
            TaskAttachmentsServiceError: Если сохранить файл не удалось.
        """
        storage_key: str | None = None
        try:
            task = await self._ensure_task_exists(task_id)
            if (
                await self.attachments_repository.get_count_for_task(task_id)
                >= self.MAX_FILES_PER_TASK
            ):
                raise TaskAttachmentLimitError(max_files=self.MAX_FILES_PER_TASK)
            original_name, extension, effective_content_type = self._validate_file(
                file_name=file_name,
                content_type=content_type,
                content=content,
            )
            storage_key = await self.storage.save(
                task_id=task_id,
                extension=extension,
                content=content,
            )
            attachment = await self.attachments_repository.save(
                task_id=task_id,
                original_name=original_name,
                storage_key=storage_key,
                content_type=effective_content_type,
                size=len(content),
            )
            logger.info(
                "✅ Файл %r добавлен к задаче id=%s. Размер: %s байт.",
                original_name,
                task_id,
                len(content),
            )
            if self.knowledge_events is not None and index_for_knowledge:
                await self.knowledge_events.upsert(
                    project_id=task.project_id,
                    entity_type=KnowledgeEntityType.ATTACHMENT,
                    entity_id=attachment.id,
                )
            await self.unit_of_work.commit()
            return self._to_schema(attachment)
        except (
            TaskNotFoundError,
            TaskAttachmentLimitError,
            TaskAttachmentTooLargeError,
            TaskAttachmentUnsupportedTypeError,
            TaskAttachmentValidationError,
        ):
            raise
        except (
            TaskAttachmentStorageError,
            TaskAttachmentsRepositoryError,
            TasksRepositoryError,
            KnowledgeEventsServiceError,
            UnitOfWorkRepositoryError,
        ) as error:
            if storage_key is not None:
                try:
                    await self.storage.delete(storage_key)
                except TaskAttachmentStorageError:
                    logger.warning(
                        "⚠️ Не удалось компенсирующе удалить файл %s.",
                        storage_key,
                        exc_info=True,
                    )
            logger.error("❌ Ошибка загрузки файла задачи id=%s.", task_id, exc_info=True)
            raise TaskAttachmentsServiceError(str(error)) from error

    async def get_attachment_content(
        self,
        *,
        task_id: int,
        attachment_id: int,
    ) -> TaskAttachmentContent:
        """Возвращает проверенный путь и метаданные файла для HTTP-ответа.

        Args:
            task_id: Идентификатор задачи.
            attachment_id: Идентификатор файла.

        Returns:
            Данные для безопасной выдачи через ``FileResponse``.

        Raises:
            TaskAttachmentNotFoundError: Если запись не найдена в этой задаче.
            TaskAttachmentsServiceError: Если файл недоступен в хранилище.
        """
        try:
            attachment = await self._get_attachment(task_id, attachment_id)
            return TaskAttachmentContent(
                path=self.storage.resolve(attachment.storage_key),
                original_name=attachment.original_name,
                content_type=attachment.content_type,
                previewable=self._is_previewable(
                    attachment.original_name,
                    attachment.content_type,
                ),
            )
        except TaskAttachmentNotFoundError:
            raise
        except (TaskAttachmentStorageError, TaskAttachmentsRepositoryError) as error:
            logger.error("❌ Файл задачи id=%s недоступен.", attachment_id, exc_info=True)
            raise TaskAttachmentsServiceError(str(error)) from error

    async def delete_attachment(self, *, task_id: int, attachment_id: int) -> None:
        """Удаляет метаданные и физический файл задачи.

        Args:
            task_id: Идентификатор задачи.
            attachment_id: Идентификатор файла.

        Raises:
            TaskAttachmentNotFoundError: Если файл не найден в этой задаче.
            TaskAttachmentsServiceError: Если удалить метаданные не удалось.
        """
        try:
            attachment = await self._get_attachment(task_id, attachment_id)
            task = await self._ensure_task_exists(task_id)
            storage_key = attachment.storage_key
            await self.attachments_repository.delete(attachment=attachment)
            if self.knowledge_events is not None:
                await self.knowledge_events.delete(
                    project_id=task.project_id,
                    entity_type=KnowledgeEntityType.ATTACHMENT,
                    entity_id=attachment_id,
                )
            await self.unit_of_work.commit()
            try:
                await self.storage.delete(storage_key)
            except TaskAttachmentStorageError:
                logger.warning(
                    "⚠️ Метаданные файла id=%s удалены, но storage key %s остался.",
                    attachment_id,
                    storage_key,
                    exc_info=True,
                )
        except TaskAttachmentNotFoundError:
            raise
        except (
            TaskAttachmentsRepositoryError,
            TasksRepositoryError,
            KnowledgeEventsServiceError,
            UnitOfWorkRepositoryError,
        ) as error:
            logger.error("❌ Ошибка удаления файла задачи id=%s.", attachment_id, exc_info=True)
            raise TaskAttachmentsServiceError(str(error)) from error

    async def _ensure_task_exists(self, task_id: int) -> Task:
        """Возвращает существующую задачу либо поднимает 404."""
        task = await self.tasks_repository.get_by_id(task_id=task_id)
        if task is None:
            raise TaskNotFoundError(task_id=task_id)
        return task

    async def _get_attachment(
        self,
        task_id: int,
        attachment_id: int,
    ) -> TaskAttachment:
        """Возвращает файл в пределах задачи либо поднимает 404."""
        attachment = await self.attachments_repository.get_by_id_for_task(
            attachment_id=attachment_id,
            task_id=task_id,
        )
        if attachment is None:
            raise TaskAttachmentNotFoundError(attachment_id=attachment_id)
        return attachment

    def _validate_file(
        self,
        *,
        file_name: str,
        content_type: str | None,
        content: bytes,
    ) -> tuple[str, str, str]:
        """Нормализует имя и проверяет размер и расширение файла."""
        if not content:
            raise TaskAttachmentValidationError("Нельзя загрузить пустой файл.")
        if len(content) > self.MAX_FILE_SIZE:
            raise TaskAttachmentTooLargeError(max_size_mb=self.MAX_FILE_SIZE // 1024 // 1024)
        original_name = Path((file_name or "").replace("\\", "/")).name.strip()
        if not original_name or "\x00" in original_name:
            raise TaskAttachmentValidationError("Имя файла некорректно.")
        if len(original_name) > 512:
            raise TaskAttachmentValidationError("Имя файла длиннее 512 символов.")
        extension = Path(original_name).suffix.lower()
        if extension not in self.ALLOWED_EXTENSIONS:
            raise TaskAttachmentUnsupportedTypeError(extension=extension)
        guessed_type = mimetypes.guess_type(original_name)[0]
        effective_content_type = (
            (content_type or guessed_type or "application/octet-stream")
            .split(";", 1)[0]
            .strip()
            .lower()
        )
        return original_name, extension, effective_content_type

    def _to_schema(self, attachment: TaskAttachment) -> TaskAttachmentSchema:
        """Дополняет ORM-модель вычисляемыми полями API."""
        return TaskAttachmentSchema(
            id=attachment.id,
            task_id=attachment.task_id,
            original_name=attachment.original_name,
            content_type=attachment.content_type,
            size=attachment.size,
            created_at=attachment.created_at,
            content_url=(f"/api/v1/tasks/{attachment.task_id}/attachments/{attachment.id}/content"),
            previewable=self._is_previewable(
                attachment.original_name,
                attachment.content_type,
            ),
        )

    def _is_previewable(self, file_name: str, content_type: str) -> bool:
        """Разрешает inline-preview только безопасных растровых изображений."""
        return Path(
            file_name
        ).suffix.lower() in self.PREVIEWABLE_EXTENSIONS and content_type.startswith("image/")
