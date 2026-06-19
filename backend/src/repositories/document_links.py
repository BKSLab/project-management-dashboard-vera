import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.db.models.document_links import DocumentLink
from src.exceptions.repositories import DocumentLinksRepositoryError

logger = logging.getLogger(__name__)


class DocumentLinksRepository:
    """Репозиторий для работы со связями документов в базе данных."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_id(self, link_id: int) -> DocumentLink | None:
        try:
            stmt = select(DocumentLink).where(DocumentLink.id == link_id)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            raise DocumentLinksRepositoryError(
                error_details=f"Ошибка при получении связи id={link_id}."
            ) from error

    async def get_for_document(self, document_id: int) -> list[DocumentLink]:
        try:
            stmt = (
                select(DocumentLink)
                .where(DocumentLink.document_id == document_id)
                .options(
                    joinedload(DocumentLink.kanban_task),
                    joinedload(DocumentLink.wbs_item),
                )
            )
            result: Result = await self.db_session.execute(stmt)
            return list(result.unique().scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise DocumentLinksRepositoryError(
                error_details=f"Ошибка при получении связей документа id={document_id}."
            ) from error

    async def get_for_task(self, kanban_task_id: int) -> list[DocumentLink]:
        try:
            stmt = (
                select(DocumentLink)
                .where(DocumentLink.kanban_task_id == kanban_task_id)
                .options(joinedload(DocumentLink.document))
            )
            result: Result = await self.db_session.execute(stmt)
            return list(result.unique().scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise DocumentLinksRepositoryError(
                error_details=f"Ошибка при получении связей задачи id={kanban_task_id}."
            ) from error

    async def create(self, data: dict) -> DocumentLink:
        try:
            link = DocumentLink(**data)
            self.db_session.add(link)
            await self.db_session.commit()
            await self.db_session.refresh(link)
            return link
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise DocumentLinksRepositoryError(error_details="Ошибка при создании связи документа.") from error

    async def delete(self, link: DocumentLink) -> None:
        try:
            await self.db_session.delete(link)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise DocumentLinksRepositoryError(
                error_details=f"Ошибка при удалении связи id={link.id}."
            ) from error
