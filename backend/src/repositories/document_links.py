import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.document_links import DocumentLink
from src.exceptions.document_links import (
    DocumentLinkAlreadyExistsRepositoryError,
    DocumentLinksRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name

logger = logging.getLogger(__name__)


class DocumentLinksRepository:
    """Репозиторий для работы со связями документов в базе данных."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_id(self, link_id: int) -> DocumentLink | None:
        """Возвращает связь документа по идентификатору.

        Args:
            link_id: Идентификатор связи.

        Returns:
            Найденная связь или ``None``.

        Raises:
            DocumentLinksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(DocumentLink).where(DocumentLink.id == link_id)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить связь документа id=%s.", link_id, exc_info=True)
            raise DocumentLinksRepositoryError(
                error_details=f"Ошибка при получении связи id={link_id}."
            ) from error

    async def get_for_document(self, document_id: int) -> list[DocumentLink]:
        """Возвращает связи указанного документа с целевыми объектами.

        Args:
            document_id: Идентификатор документа.

        Returns:
            Связи документа.

        Raises:
            DocumentLinksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(DocumentLink).where(DocumentLink.document_id == document_id)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить связи документа id=%s.", document_id, exc_info=True
            )
            raise DocumentLinksRepositoryError(
                error_details=f"Ошибка при получении связей документа id={document_id}."
            ) from error

    async def get_for_task(self, kanban_task_id: int) -> list[DocumentLink]:
        """Возвращает связи документов с указанной задачей.

        Args:
            kanban_task_id: Идентификатор задачи.

        Returns:
            Связи документов с задачей.

        Raises:
            DocumentLinksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(DocumentLink).where(DocumentLink.kanban_task_id == kanban_task_id)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить связи задачи id=%s.", kanban_task_id, exc_info=True
            )
            raise DocumentLinksRepositoryError(
                error_details=f"Ошибка при получении связей задачи id={kanban_task_id}."
            ) from error

    async def create(self, data: dict) -> DocumentLink:
        """Создаёт связь документа и возвращает сохранённую модель.

        Args:
            data: Поля новой связи.

        Returns:
            Сохранённая связь.

        Raises:
            DocumentLinksRepositoryError: Если сохранить связь не удалось.
        """
        try:
            link = DocumentLink(**data)
            self.db_session.add(link)
            await self.db_session.commit()
            await self.db_session.refresh(link)
            return link
        except IntegrityError as error:
            await self.db_session.rollback()
            constraint_name = get_integrity_constraint_name(error)
            if constraint_name in {
                "uq_document_links_document_task",
                "uq_document_links_document_wbs",
            }:
                logger.warning("⚠️ Связь документа id=%s уже существует.", data["document_id"])
                raise DocumentLinkAlreadyExistsRepositoryError(
                    document_id=data["document_id"]
                ) from error
            logger.error("❌ Ограничение БД не позволило создать связь документа.", exc_info=True)
            raise DocumentLinksRepositoryError(
                error_details="Ошибка ограничения БД при создании связи документа."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось создать связь документа.", exc_info=True)
            raise DocumentLinksRepositoryError(
                error_details="Ошибка при создании связи документа."
            ) from error

    async def delete(self, link: DocumentLink) -> None:
        """Удаляет связь документа.

        Args:
            link: Удаляемая ORM-модель связи.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            DocumentLinksRepositoryError: Если удалить связь не удалось.
        """
        try:
            await self.db_session.delete(link)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить связь документа id=%s.", link.id, exc_info=True)
            raise DocumentLinksRepositoryError(
                error_details=f"Ошибка при удалении связи id={link.id}."
            ) from error
