import logging

from sqlalchemy import Result, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.wbs import WbsItem
from src.exceptions.wbs import WbsCodeAlreadyExistsRepositoryError, WbsRepositoryError
from src.utils.db_errors import get_integrity_constraint_name

logger = logging.getLogger(__name__)


class WbsRepository:
    """Репозиторий для работы с деревом ИСР в базе данных."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all_items(self) -> list[WbsItem]:
        """Возвращает все узлы ИСР в порядке отображения.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Список узлов ИСР.

        Raises:
            WbsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(WbsItem).order_by(WbsItem.order_index)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить дерево ИСР.", exc_info=True)
            raise WbsRepositoryError(error_details="Ошибка при получении дерева ИСР.") from error

    async def get_by_id(self, item_id: int) -> WbsItem | None:
        """Возвращает узел ИСР по идентификатору.

        Args:
            item_id: Идентификатор узла.

        Returns:
            Найденный узел или ``None``.

        Raises:
            WbsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(WbsItem).where(WbsItem.id == item_id)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить узел ИСР id=%s.", item_id, exc_info=True)
            raise WbsRepositoryError(
                error_details=f"Ошибка при получении узла ИСР id={item_id}."
            ) from error

    async def get_by_ids(self, item_ids: set[int]) -> list[WbsItem]:
        """Возвращает узлы ИСР по набору идентификаторов.

        Args:
            item_ids: Идентификаторы узлов.

        Returns:
            Найденные узлы ИСР.

        Raises:
            WbsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not item_ids:
            return []
        try:
            result: Result = await self.db_session.execute(
                select(WbsItem).where(WbsItem.id.in_(item_ids))
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить набор узлов ИСР.", exc_info=True)
            raise WbsRepositoryError("Ошибка получения набора узлов ИСР.") from error

    async def get_children(self, parent_id: int | None) -> list[WbsItem]:
        """Возвращает прямых потомков узла.

        Args:
            parent_id: Родительский узел или ``None`` для корневого уровня.

        Returns:
            Дочерние узлы в порядке отображения.

        Raises:
            WbsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = (
                select(WbsItem).where(WbsItem.parent_id == parent_id).order_by(WbsItem.order_index)
            )
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить потомков ИСР parent_id=%s.", parent_id, exc_info=True
            )
            raise WbsRepositoryError(
                error_details=f"Ошибка при получении потомков узла parent_id={parent_id}."
            ) from error

    async def get_ids_by_code_search(self, search: str) -> set[int]:
        """Возвращает id узлов ИСР, код которых содержит поисковую строку.

        Args:
            search: Фрагмент кода ИСР.

        Returns:
            Идентификаторы найденных узлов.

        Raises:
            WbsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            escaped_code = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = select(WbsItem.id).where(WbsItem.code.ilike(f"%{escaped_code}%", escape="\\"))
            result: Result = await self.db_session.execute(stmt)
            return set(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось выполнить поиск по кодам ИСР.", exc_info=True)
            raise WbsRepositoryError("Ошибка поиска по кодам ИСР.") from error

    async def get_count(self) -> int:
        """Возвращает количество узлов ИСР.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Количество узлов.

        Raises:
            WbsRepositoryError: Если подсчёт завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(func.count()).select_from(WbsItem)
            )
            return result.scalar_one()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подсчитать узлы ИСР.", exc_info=True)
            raise WbsRepositoryError("Ошибка подсчёта узлов ИСР.") from error

    async def create_item(self, data: dict) -> WbsItem:
        """Создаёт узел ИСР.

        Args:
            data: Поля нового узла.

        Returns:
            Сохранённый узел.

        Raises:
            WbsRepositoryError: Если сохранить узел не удалось.
        """
        try:
            item = WbsItem(**data)
            self.db_session.add(item)
            await self.db_session.commit()
            await self.db_session.refresh(item)
            return item
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) == "uq_wbs_items_code":
                logger.warning("⚠️ Узел ИСР с кодом %s уже существует.", data["code"])
                raise WbsCodeAlreadyExistsRepositoryError(code=data["code"]) from error
            logger.error("❌ Ограничение БД не позволило создать узел ИСР.", exc_info=True)
            raise WbsRepositoryError("Ошибка ограничения БД при создании узла ИСР.") from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось создать узел ИСР.", exc_info=True)
            raise WbsRepositoryError(error_details="Ошибка при создании узла ИСР.") from error

    async def update_item(self, item: WbsItem, data: dict) -> WbsItem:
        """Обновляет поля узла ИСР.

        Args:
            item: Изменяемая ORM-модель узла.
            data: Новые значения полей.

        Returns:
            Обновлённый узел.

        Raises:
            WbsCodeAlreadyExistsRepositoryError: Если новый код уже занят.
            WbsRepositoryError: Если обновить узел не удалось.
        """
        new_code = data.get("code")
        try:
            for field, value in data.items():
                setattr(item, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(item)
            return item
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) == "uq_wbs_items_code" and isinstance(
                new_code, str
            ):
                logger.warning("⚠️ Узел ИСР с кодом %s уже существует.", new_code)
                raise WbsCodeAlreadyExistsRepositoryError(code=new_code) from error
            logger.error(
                "❌ Ограничение БД не позволило обновить узел ИСР id=%s.",
                item.id,
                exc_info=True,
            )
            raise WbsRepositoryError(
                error_details=f"Ошибка ограничения БД при обновлении узла ИСР id={item.id}."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить узел ИСР id=%s.", item.id, exc_info=True)
            raise WbsRepositoryError(
                error_details=f"Ошибка при обновлении узла ИСР id={item.id}."
            ) from error

    async def delete_item(self, item: WbsItem) -> None:
        """Удаляет узел ИСР с каскадным удалением потомков.

        Args:
            item: Удаляемая ORM-модель узла.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            WbsRepositoryError: Если удалить узел не удалось.
        """
        try:
            await self.db_session.delete(item)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить узел ИСР id=%s.", item.id, exc_info=True)
            raise WbsRepositoryError(
                error_details=f"Ошибка при удалении узла ИСР id={item.id}."
            ) from error
