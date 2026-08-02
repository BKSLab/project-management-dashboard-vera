import logging
import re

from src.exceptions.documents import (
    DocumentNotFoundError,
    DocumentSlugAlreadyExistsRepositoryError,
    DocumentSlugConflictError,
    DocumentsRepositoryError,
    DocumentsServiceError,
)
from src.repositories.documents import DocumentsRepository
from src.schemas.documents import DocumentDetailSchema, DocumentSchema

logger = logging.getLogger(__name__)


def slugify(title: str) -> str:
    """Преобразует заголовок в slug, сохраняя кириллицу (URL поддерживает unicode)."""
    slug = title.strip().lower()
    slug = re.sub(r"[^\w]+", "-", slug, flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "document"


class DocumentsService:
    """Сервис для работы с документами."""

    def __init__(self, documents_repository: DocumentsRepository):
        self.documents_repository = documents_repository

    async def get_document_list(self, search: str | None = None) -> list[DocumentSchema]:
        """Возвращает документы с опциональными поисковыми фрагментами.

        Args:
            search: Опциональная строка полнотекстового поиска.

        Returns:
            Список документов.

        Raises:
            DocumentsServiceError: Если получить документы не удалось.
        """
        try:
            documents = await self.documents_repository.get_all(search=search)
            search_highlights = (
                await self.documents_repository.get_search_highlights(
                    document_ids=[document.id for document in documents],
                    search=search,
                )
                if search and search.strip()
                else {}
            )
            result = []
            for document in documents:
                schema = DocumentSchema.model_validate(document)
                for field, value in search_highlights.get(document.id, {}).items():
                    setattr(schema, field, value)
                result.append(schema)
            return result
        except DocumentsRepositoryError as error:
            logger.error("❌ Ошибка получения документов.", exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def get_document_by_slug(self, slug: str) -> DocumentDetailSchema:
        """Возвращает документ по slug.

        Args:
            slug: URL-идентификатор документа.

        Returns:
            Полное представление документа.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            DocumentsServiceError: Если получить документ не удалось.
        """
        try:
            document = await self.documents_repository.get_by_slug(slug=slug)
            if document is None:
                raise DocumentNotFoundError(slug=slug)
            return DocumentDetailSchema.model_validate(document)
        except DocumentNotFoundError:
            raise
        except DocumentsRepositoryError as error:
            logger.error("❌ Ошибка получения документа slug=%s.", slug, exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def update_document(self, slug: str, data: dict) -> DocumentDetailSchema:
        """Обновляет документ и возвращает актуальное состояние.

        Args:
            slug: URL-идентификатор документа.
            data: Изменяемые поля документа.

        Returns:
            Обновлённый документ.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            DocumentSlugConflictError: Если новый slug уже занят.
            DocumentsServiceError: Если обновить документ не удалось.
        """
        try:
            document = await self.documents_repository.get_by_slug(slug=slug)
            if document is None:
                raise DocumentNotFoundError(slug=slug)
            updated = await self.documents_repository.update(document=document, data=data)
            return DocumentDetailSchema.model_validate(updated)
        except DocumentSlugAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт slug при обновлении документа: %s.", error.slug)
            raise DocumentSlugConflictError(slug=error.slug) from error
        except DocumentNotFoundError:
            raise
        except DocumentsRepositoryError as error:
            logger.error("❌ Ошибка обновления документа slug=%s.", slug, exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def create_document(
        self, title: str, slug: str | None, content_md: str
    ) -> DocumentDetailSchema:
        """Создаёт документ, подбирая свободный slug при необходимости.

        Args:
            title: Заголовок документа.
            slug: Желаемый URL-идентификатор или ``None``.
            content_md: Markdown-содержимое документа.

        Returns:
            Созданный документ.

        Raises:
            DocumentSlugConflictError: Если уникальный slug заняли конкурентно.
            DocumentsServiceError: Если создать документ не удалось.
        """
        try:
            base_slug = slugify(slug) if slug else slugify(title)
            candidate = base_slug
            suffix = 2
            while await self.documents_repository.get_by_slug(slug=candidate) is not None:
                candidate = f"{base_slug}-{suffix}"
                suffix += 1
            document = await self.documents_repository.create(
                slug=candidate,
                title=title,
                content_md=content_md,
            )
            return DocumentDetailSchema.model_validate(document)
        except DocumentSlugAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт slug при создании документа: %s.", error.slug)
            raise DocumentSlugConflictError(slug=error.slug) from error
        except DocumentsRepositoryError as error:
            logger.error("❌ Ошибка создания документа.", exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def delete_document(self, slug: str) -> None:
        """Удаляет документ.

        Args:
            slug: URL-идентификатор документа.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            DocumentsServiceError: Если удалить документ не удалось.
        """
        try:
            document = await self.documents_repository.get_by_slug(slug=slug)
            if document is None:
                raise DocumentNotFoundError(slug=slug)
            await self.documents_repository.delete(document=document)
        except DocumentNotFoundError:
            raise
        except DocumentsRepositoryError as error:
            logger.error("❌ Ошибка удаления документа slug=%s.", slug, exc_info=True)
            raise DocumentsServiceError(str(error)) from error
