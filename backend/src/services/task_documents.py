from __future__ import annotations

import logging
from pathlib import Path

from src.clients.vision import VisionCapability
from src.exceptions.base import ServiceError
from src.exceptions.clients import ClientError
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.documents import DocumentsServiceError
from src.exceptions.knowledge import KnowledgeProviderError
from src.exceptions.storage import StorageError
from src.exceptions.task_attachments import TaskAttachmentsServiceError
from src.exceptions.task_documents import (
    TaskDocumentStepFailedError,
    TaskDocumentTaskNotFoundError,
    TaskDocumentTooLargeError,
    TaskDocumentUnsupportedFormatError,
    TaskDocumentValidationError,
)
from src.exceptions.tasks import TasksRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.knowledge.extract import INDEXABLE_EXTENSIONS, extract_indexable_text
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.task_documents import TaskDocumentImportSchema
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.task_attachments import TaskAttachmentsService
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)

UNSUPPORTED_FORMAT_MESSAGE = (
    "Этот формат нельзя преобразовать в документ проекта. "
    "Поддерживаются PDF, DOCX, TXT, Markdown, CSV, Excel и изображения."
)

# Ошибки вложенных сервисов, которые верхний сервис обязан преобразовать
# в свою иерархию. Перечислены явно: широкий `ApplicationError` скрыл бы
# появление нового семейства у зависимости.
NESTED_SERVICE_ERRORS = (
    TaskAttachmentsServiceError,
    DocumentsServiceError,
    DocumentLinksServiceError,
)


class TaskDocumentImportService:
    """Импортирует файл как оригинал задачи и текстовый документ проекта.

    Наружу сервис отдаёт только собственные ошибки: эндпоинту не нужно
    знать, из скольких вложенных сервисов собран сценарий.
    """

    def __init__(
        self,
        *,
        tasks_repository: TasksRepository,
        attachments_service: TaskAttachmentsService,
        documents_service: DocumentsService,
        links_service: DocumentLinksService,
        unit_of_work: UnitOfWork,
        attachment_storage: TaskAttachmentStorage,
        vision: VisionCapability,
        extract_max_chars: int,
    ) -> None:
        self.tasks_repository = tasks_repository
        self.attachments_service = attachments_service
        self.documents_service = documents_service
        self.links_service = links_service
        self.unit_of_work = unit_of_work
        self.attachment_storage = attachment_storage
        self.vision = vision
        self.extract_max_chars = extract_max_chars

    @property
    def max_file_size(self) -> int:
        """Предел размера исходного файла."""
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
        """Сохраняет исходник, извлекает текст и создаёт связь документа с задачей.

        Args:
            task_id: Задача, в которую импортируется документ.
            user_id: Пользователь, выполняющий импорт.
            file_name: Исходное имя файла.
            content_type: MIME-тип, заявленный клиентом.
            content: Бинарное содержимое файла.

        Returns:
            Созданные оригинал, документ проекта и их связь.

        Raises:
            TaskDocumentTaskNotFoundError: Если задача не найдена.
            TaskDocumentValidationError: Если файл пуст или имя некорректно.
            TaskDocumentTooLargeError: Если файл превышает лимит.
            TaskDocumentUnsupportedFormatError: Если формат не индексируется
                или в файле не нашлось текста.
            TaskDocumentStepFailedError: Если отказал вложенный шаг импорта.
            KnowledgeProviderError: Если vision-модель недоступна.
        """
        task = await self._get_task(task_id)
        safe_name = self._validate(file_name=file_name, content=content)
        extracted = await self._extract_text(safe_name=safe_name, content=content)

        storage_key: str | None = None
        try:
            # Три записи — один бизнес-факт, поэтому и транзакция одна:
            # вложенные сервисы не фиксируют свою часть сами.
            stored = await self.attachments_service.save_in_transaction(
                task_id=task_id,
                file_name=safe_name,
                content_type=content_type,
                content=content,
                index_for_knowledge=False,
            )
            storage_key = stored.storage_key
            title = safe_name[:255]
            document = await self.documents_service.create_document(
                project_id=task.project_id,
                title=title,
                slug=None,
                content_md=_document_markdown(title=title, content=extracted),
                commit=False,
            )
            link = await self.links_service.create_link(
                document_id=document.id,
                task_id=task_id,
                user_id=user_id,
                commit=False,
            )
            await self.unit_of_work.commit()
            return TaskDocumentImportSchema(
                attachment=stored.attachment,
                document=document,
                link=link,
            )
        except BaseException as error:
            # Откат снимает все записи разом; компенсировать нужно только
            # то, что база откатить не может, — физический файл.
            await self._rollback()
            await self._remove_stored_file(storage_key)
            if isinstance(error, NESTED_SERVICE_ERRORS):
                raise TaskDocumentStepFailedError(error) from error
            raise

    async def _get_task(self, task_id: int):
        """Читает задачу импорта и переводит ошибку репозитория в свою."""
        try:
            task = await self.tasks_repository.get_by_id(task_id=task_id)
        except TasksRepositoryError as error:
            logger.error("❌ Не удалось прочитать задачу id=%s.", task_id, exc_info=True)
            raise TaskDocumentStepFailedError(_as_service_error(error)) from error
        if task is None:
            raise TaskDocumentTaskNotFoundError(task_id=task_id)
        return task

    def _validate(self, *, file_name: str, content: bytes) -> str:
        """Проверяет файл до любых записей и возвращает безопасное имя."""
        safe_name = Path((file_name or "").replace("\\", "/")).name.strip()
        if not content:
            raise TaskDocumentValidationError("Нельзя загрузить пустой файл.")
        if len(content) > self.max_file_size:
            raise TaskDocumentTooLargeError(max_size_mb=self.max_file_size // 1024 // 1024)
        if not safe_name or "\x00" in safe_name:
            raise TaskDocumentValidationError("Имя файла некорректно.")
        if Path(safe_name).suffix.lower() not in INDEXABLE_EXTENSIONS:
            raise TaskDocumentUnsupportedFormatError(UNSUPPORTED_FORMAT_MESSAGE)
        return safe_name

    async def _extract_text(self, *, safe_name: str, content: bytes) -> str:
        """Извлекает текст файла до начала записи."""
        try:
            extracted = await extract_indexable_text(
                safe_name,
                content,
                vision=self.vision,
                max_chars=self.extract_max_chars,
            )
        except ValueError as error:
            raise TaskDocumentUnsupportedFormatError(
                f"Не удалось прочитать «{safe_name}»: файл повреждён или имеет неверный формат."
            ) from error
        except ClientError as error:
            logger.error("❌ Vision недоступен при импорте документа.", exc_info=True)
            raise KnowledgeProviderError(str(error)) from error
        if not extracted:
            raise TaskDocumentUnsupportedFormatError(
                f"В «{safe_name}» не удалось найти текст для документа проекта."
            )
        return extracted

    async def _rollback(self) -> None:
        """Откатывает транзакцию импорта, не маскируя исходную ошибку."""
        try:
            await self.unit_of_work.rollback()
        except UnitOfWorkRepositoryError:
            logger.warning("⚠️ Не удалось откатить транзакцию импорта документа.", exc_info=True)

    async def _remove_stored_file(self, storage_key: str | None) -> None:
        """Удаляет физический файл: его откат транзакции не затрагивает.

        Метаданные исчезнут вместе с откатом, а файл на диске останется
        сиротой, если его не убрать здесь.
        """
        if storage_key is None:
            return
        try:
            await self.attachment_storage.delete(storage_key)
        except StorageError:
            logger.warning(
                "⚠️ Не удалось удалить файл %s после отката импорта.",
                storage_key,
                exc_info=True,
            )


def _as_service_error(error: Exception) -> ServiceError:
    """Оборачивает ошибку нижнего слоя в носитель статуса и формулировки."""
    carrier = ServiceError(str(error))
    return carrier


def _document_markdown(*, title: str, content: str) -> str:
    """Собирает Markdown документа, не дублируя заголовок для .md файлов."""
    normalized = content.strip()
    if Path(title).suffix.lower() == ".md":
        return normalized
    return f"# {title}\n\n{normalized}"
