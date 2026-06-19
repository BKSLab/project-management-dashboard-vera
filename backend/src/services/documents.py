import logging
import re

from src.exceptions.services import DocumentNotFoundError
from src.repositories.documents import DocumentsRepository
from src.schemas.documents import DocumentDetailSchema, DocumentSchema

logger = logging.getLogger(__name__)


def slugify(title: str) -> str:
    """Преобразует заголовок в slug, сохраняя кириллицу (URL поддерживает unicode)."""
    slug = title.strip().lower()
    slug = re.sub(r'[^\w]+', '-', slug, flags=re.UNICODE)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or 'document'


class DocumentsService:
    """Сервис для работы с документами."""

    def __init__(self, documents_repository: DocumentsRepository):
        self.documents_repository = documents_repository

    async def get_document_list(self) -> list[DocumentSchema]:
        """Возвращает список всех документов."""
        documents = await self.documents_repository.get_all()
        return [DocumentSchema.model_validate(document) for document in documents]

    async def get_document_by_slug(self, slug: str) -> DocumentDetailSchema:
        """Возвращает документ по slug или поднимает DocumentNotFoundError."""
        document = await self.documents_repository.get_by_slug(slug=slug)
        if document is None:
            raise DocumentNotFoundError(slug=slug)
        return DocumentDetailSchema.model_validate(document)

    async def update_document(self, slug: str, data: dict) -> DocumentDetailSchema:
        """Обновляет документ и возвращает актуальное состояние."""
        document = await self.documents_repository.get_by_slug(slug=slug)
        if document is None:
            raise DocumentNotFoundError(slug=slug)

        updated = await self.documents_repository.update(document=document, data=data)
        return DocumentDetailSchema.model_validate(updated)

    async def create_document(
        self, title: str, slug: str | None, content_md: str
    ) -> DocumentDetailSchema:
        """Создаёт документ. Если slug не передан или занят, подбирает свободный вариант."""
        base_slug = slugify(slug) if slug else slugify(title)
        candidate = base_slug
        suffix = 2
        while await self.documents_repository.get_by_slug(slug=candidate) is not None:
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        document = await self.documents_repository.create(
            slug=candidate, title=title, content_md=content_md
        )
        return DocumentDetailSchema.model_validate(document)

    async def delete_document(self, slug: str) -> None:
        """Удаляет документ."""
        document = await self.documents_repository.get_by_slug(slug=slug)
        if document is None:
            raise DocumentNotFoundError(slug=slug)
        await self.documents_repository.delete(document=document)
