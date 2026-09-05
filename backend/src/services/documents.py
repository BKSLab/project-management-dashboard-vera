import logging
import re

from src.db.models.knowledge_index_jobs import KnowledgeEntityType
from src.exceptions.documents import (
    DocumentNotFoundError,
    DocumentSlugAlreadyExistsRepositoryError,
    DocumentSlugConflictError,
    DocumentsRepositoryError,
    DocumentsServiceError,
)
from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.projects import ProjectNotFoundError, ProjectsRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.repositories.documents import DocumentsRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.documents import DocumentDetailSchema, DocumentSchema
from src.services.knowledge_events import KnowledgeEvents

logger = logging.getLogger(__name__)

RepositoryErrors = (
    DocumentsRepositoryError,
    ProjectsRepositoryError,
    KnowledgeEventsServiceError,
    UnitOfWorkRepositoryError,
)


def slugify(title: str) -> str:
    """Преобразует заголовок в slug, сохраняя кириллицу (URL поддерживает unicode)."""
    slug = title.strip().lower()
    slug = re.sub(r"[^\w]+", "-", slug, flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "document"


class DocumentsService:
    """Сервис для работы с документами проекта."""

    def __init__(
        self,
        documents_repository: DocumentsRepository,
        projects_repository: ProjectsRepository,
        unit_of_work: UnitOfWork,
        knowledge_events: KnowledgeEvents | None = None,
    ):
        self.documents_repository = documents_repository
        self.projects_repository = projects_repository
        self.unit_of_work = unit_of_work
        self.knowledge_events = knowledge_events

    async def get_document_list(
        self,
        project_id: int,
        search: str | None = None,
    ) -> list[DocumentSchema]:
        """Возвращает документы проекта с опциональными поисковыми фрагментами.

        Args:
            project_id: Идентификатор проекта.
            search: Опциональная строка полнотекстового поиска.

        Returns:
            Список документов проекта.

        Raises:
            ProjectNotFoundError: Если проект не найден.
            DocumentsServiceError: Если получить документы не удалось.
        """
        try:
            await self._ensure_project_exists(project_id=project_id)
            documents = await self.documents_repository.get_by_project(
                project_id=project_id,
                search=search,
            )
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
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения документов проекта id=%s.", project_id, exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def get_document(self, document_id: int) -> DocumentDetailSchema:
        """Возвращает документ по идентификатору.

        Args:
            document_id: Идентификатор документа.

        Returns:
            Полное представление документа.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            DocumentsServiceError: Если получить документ не удалось.
        """
        try:
            document = await self.documents_repository.get_by_id(document_id=document_id)
            if document is None:
                raise DocumentNotFoundError(document_id=document_id)
            return DocumentDetailSchema.model_validate(document)
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения документа id=%s.", document_id, exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def create_document(
        self,
        project_id: int,
        title: str,
        slug: str | None,
        content_md: str,
    ) -> DocumentDetailSchema:
        """Создаёт документ проекта, подбирая свободный slug при необходимости.

        Args:
            project_id: Идентификатор проекта.
            title: Заголовок документа.
            slug: Желаемый URL-идентификатор или ``None``.
            content_md: Markdown-содержимое документа.

        Returns:
            Созданный документ.

        Raises:
            ProjectNotFoundError: Если проект не найден.
            DocumentSlugConflictError: Если уникальный slug заняли конкурентно.
            DocumentsServiceError: Если создать документ не удалось.
        """
        try:
            await self._ensure_project_exists(project_id=project_id)
            candidate = await self._allocate_slug(
                project_id=project_id,
                slug=slug,
                title=title,
            )
            document = await self.documents_repository.create(
                data={
                    "project_id": project_id,
                    "slug": candidate,
                    "title": title,
                    "content_md": content_md,
                }
            )
            if self.knowledge_events is not None:
                await self.knowledge_events.upsert(
                    project_id=project_id,
                    entity_type=KnowledgeEntityType.DOCUMENT,
                    entity_id=document.id,
                )
            await self.unit_of_work.commit()
            return DocumentDetailSchema.model_validate(document)
        except DocumentSlugAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт slug при создании документа: %s.", error.slug)
            raise DocumentSlugConflictError(slug=error.slug) from error
        except RepositoryErrors as error:
            logger.error("❌ Ошибка создания документа в проекте id=%s.", project_id, exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def update_document(self, document_id: int, data: dict) -> DocumentDetailSchema:
        """Обновляет документ и возвращает актуальное состояние.

        Args:
            document_id: Идентификатор документа.
            data: Изменяемые поля документа.

        Returns:
            Обновлённый документ.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            DocumentSlugConflictError: Если новый slug уже занят.
            DocumentsServiceError: Если обновить документ не удалось.
        """
        try:
            document = await self.documents_repository.get_by_id(document_id=document_id)
            if document is None:
                raise DocumentNotFoundError(document_id=document_id)
            updated = await self.documents_repository.update(document=document, data=data)
            if self.knowledge_events is not None:
                await self.knowledge_events.upsert(
                    project_id=updated.project_id,
                    entity_type=KnowledgeEntityType.DOCUMENT,
                    entity_id=updated.id,
                )
            await self.unit_of_work.commit()
            return DocumentDetailSchema.model_validate(updated)
        except DocumentSlugAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт slug при обновлении документа: %s.", error.slug)
            raise DocumentSlugConflictError(slug=error.slug) from error
        except RepositoryErrors as error:
            logger.error("❌ Ошибка обновления документа id=%s.", document_id, exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def delete_document(self, document_id: int) -> None:
        """Удаляет документ.

        Args:
            document_id: Идентификатор документа.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            DocumentsServiceError: Если удалить документ не удалось.
        """
        try:
            document = await self.documents_repository.get_by_id(document_id=document_id)
            if document is None:
                raise DocumentNotFoundError(document_id=document_id)
            project_id = document.project_id
            await self.documents_repository.delete(document=document)
            if self.knowledge_events is not None:
                await self.knowledge_events.delete(
                    project_id=project_id,
                    entity_type=KnowledgeEntityType.DOCUMENT,
                    entity_id=document_id,
                )
            await self.unit_of_work.commit()
        except RepositoryErrors as error:
            logger.error("❌ Ошибка удаления документа id=%s.", document_id, exc_info=True)
            raise DocumentsServiceError(str(error)) from error

    async def _allocate_slug(self, project_id: int, slug: str | None, title: str) -> str:
        """Подбирает свободный slug внутри проекта."""
        base_slug = slugify(slug) if slug else slugify(title)
        candidate = base_slug
        suffix = 2
        while (
            await self.documents_repository.get_by_project_slug(
                project_id=project_id,
                slug=candidate,
            )
            is not None
        ):
            candidate = f"{base_slug}-{suffix}"
            suffix += 1
        return candidate

    async def _ensure_project_exists(self, project_id: int) -> None:
        """Проверяет существование проекта перед операцией с документами."""
        if await self.projects_repository.get_by_id(project_id=project_id) is None:
            raise ProjectNotFoundError(project_id=project_id)
