import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.documents import Document
from src.exceptions.repositories import DocumentsRepositoryError

logger = logging.getLogger(__name__)


class DocumentsRepository:
    """Репозиторий для работы с документами в базе данных."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[Document]:
        """Возвращает список всех документов."""
        try:
            stmt = select(Document).order_by(Document.title)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise DocumentsRepositoryError(
                error_details="Ошибка при получении списка документов."
            ) from error

    async def get_by_slug(self, slug: str) -> Document | None:
        """Возвращает документ по slug."""
        try:
            stmt = select(Document).where(Document.slug == slug)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            raise DocumentsRepositoryError(
                error_details=f"Ошибка при получении документа. slug={slug}."
            ) from error

    async def create(self, slug: str, title: str, content_md: str) -> Document:
        """Создаёт новый документ."""
        try:
            document = Document(slug=slug, title=title, content_md=content_md)
            self.db_session.add(document)
            await self.db_session.commit()
            await self.db_session.refresh(document)
            return document
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise DocumentsRepositoryError(
                error_details=f"Ошибка при создании документа. slug={slug}."
            ) from error

    async def update(self, document: Document, data: dict) -> Document:
        """Обновляет поля документа и сохраняет изменения."""
        try:
            for field, value in data.items():
                setattr(document, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(document)
            return document
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise DocumentsRepositoryError(
                error_details=f"Ошибка при обновлении документа. id={document.id}."
            ) from error

    async def delete(self, document: Document) -> None:
        """Удаляет документ."""
        try:
            await self.db_session.delete(document)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise DocumentsRepositoryError(
                error_details=f"Ошибка при удалении документа. id={document.id}."
            ) from error
