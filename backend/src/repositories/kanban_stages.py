import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.kanban_stages import KanbanStage
from src.exceptions.kanban_stages import KanbanStagesRepositoryError

logger = logging.getLogger(__name__)


class KanbanStagesRepository:
    """Репозиторий стадий канбан-доски."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[KanbanStage]:
        """Возвращает стадии в порядке отображения.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Список стадий канбан-доски.

        Raises:
            KanbanStagesRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(KanbanStage).order_by(KanbanStage.order_index)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить стадии канбана.", exc_info=True)
            raise KanbanStagesRepositoryError("Ошибка получения списка стадий.") from error

    async def get_by_id(self, stage_id: int) -> KanbanStage | None:
        """Возвращает стадию по идентификатору.

        Args:
            stage_id: Идентификатор стадии.

        Returns:
            Найденная стадия или ``None``.

        Raises:
            KanbanStagesRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(KanbanStage).where(KanbanStage.id == stage_id)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить стадию id=%s.", stage_id, exc_info=True)
            raise KanbanStagesRepositoryError(f"Ошибка получения стадии id={stage_id}.") from error

    async def save(self, data: dict) -> KanbanStage:
        """Создаёт стадию и возвращает сохранённую модель.

        Args:
            data: Поля новой стадии.

        Returns:
            Сохранённая стадия.

        Raises:
            KanbanStagesRepositoryError: Если сохранить стадию не удалось.
        """
        try:
            stage = KanbanStage(**data)
            self.db_session.add(stage)
            await self.db_session.commit()
            await self.db_session.refresh(stage)
            return stage
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить стадию канбана.", exc_info=True)
            raise KanbanStagesRepositoryError("Ошибка сохранения стадии.") from error

    async def update(self, stage: KanbanStage, data: dict) -> KanbanStage:
        """Обновляет стадию и возвращает сохранённую модель.

        Args:
            stage: Изменяемая ORM-модель стадии.
            data: Новые значения полей.

        Returns:
            Обновлённая стадия.

        Raises:
            KanbanStagesRepositoryError: Если обновить стадию не удалось.
        """
        try:
            for field, value in data.items():
                setattr(stage, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(stage)
            return stage
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить стадию id=%s.", stage.id, exc_info=True)
            raise KanbanStagesRepositoryError(f"Ошибка обновления стадии id={stage.id}.") from error

    async def delete(self, stage: KanbanStage) -> None:
        """Удаляет стадию.

        Args:
            stage: Удаляемая ORM-модель стадии.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            KanbanStagesRepositoryError: Если удалить стадию не удалось.
        """
        try:
            await self.db_session.delete(stage)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить стадию id=%s.", stage.id, exc_info=True)
            raise KanbanStagesRepositoryError(f"Ошибка удаления стадии id={stage.id}.") from error
