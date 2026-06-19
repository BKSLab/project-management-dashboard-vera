import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.db.models.kanban import KanbanTask
from src.db.models.wbs import WbsItem
from src.exceptions.repositories import WbsRepositoryError

logger = logging.getLogger(__name__)


class WbsRepository:
    """Репозиторий для работы с деревом ИСР в базе данных."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all_items(self) -> list[WbsItem]:
        """Возвращает все узлы ИСР с подгруженной задачей канбана и её стадией."""
        try:
            stmt = (
                select(WbsItem)
                .options(joinedload(WbsItem.task).joinedload(KanbanTask.stage))
                .order_by(WbsItem.order_index)
            )
            result: Result = await self.db_session.execute(stmt)
            return list(result.unique().scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise WbsRepositoryError(error_details="Ошибка при получении дерева ИСР.") from error

    async def get_by_id(self, item_id: int) -> WbsItem | None:
        """Возвращает узел ИСР по id с подгруженной связанной задачей канбана."""
        try:
            stmt = (
                select(WbsItem)
                .where(WbsItem.id == item_id)
                .options(joinedload(WbsItem.task))
            )
            result: Result = await self.db_session.execute(stmt)
            return result.unique().scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            raise WbsRepositoryError(error_details=f"Ошибка при получении узла ИСР id={item_id}.") from error

    async def get_children(self, parent_id: int | None) -> list[WbsItem]:
        """Возвращает прямых потомков узла (или узлы верхнего уровня, если parent_id=None)."""
        try:
            stmt = select(WbsItem).where(WbsItem.parent_id == parent_id).order_by(WbsItem.order_index)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise WbsRepositoryError(
                error_details=f"Ошибка при получении потомков узла parent_id={parent_id}."
            ) from error

    async def create_item(self, data: dict) -> WbsItem:
        """Создаёт узел ИСР."""
        try:
            item = WbsItem(**data)
            self.db_session.add(item)
            await self.db_session.commit()
            await self.db_session.refresh(item)
            return item
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise WbsRepositoryError(error_details="Ошибка при создании узла ИСР.") from error

    async def update_item(self, item: WbsItem, data: dict) -> WbsItem:
        """Обновляет поля узла ИСР."""
        try:
            for field, value in data.items():
                setattr(item, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(item)
            return item
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise WbsRepositoryError(error_details=f"Ошибка при обновлении узла ИСР id={item.id}.") from error

    async def delete_item(self, item: WbsItem) -> None:
        """Удаляет узел ИСР (потомки удаляются каскадно на уровне БД)."""
        try:
            await self.db_session.delete(item)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise WbsRepositoryError(error_details=f"Ошибка при удалении узла ИСР id={item.id}.") from error
