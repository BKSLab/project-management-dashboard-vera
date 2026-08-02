import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.seed_state import SeedState
from src.exceptions.initial_data import (
    SeedStateAlreadyExistsRepositoryError,
    SeedStateRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name

logger = logging.getLogger(__name__)


class SeedStateRepository:
    """Репозиторий маркеров одноразовой загрузки начальных данных."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_key(self, key: str) -> SeedState | None:
        """Возвращает маркер загрузки по ключу.

        Args:
            key: Версионированный ключ набора данных.

        Returns:
            Маркер загрузки или ``None``.

        Raises:
            SeedStateRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(SeedState).where(SeedState.key == key)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить маркер загрузки %s.", key, exc_info=True)
            raise SeedStateRepositoryError(f"Ошибка получения маркера загрузки {key}.") from error

    async def save(self, key: str) -> SeedState:
        """Сохраняет маркер успешной загрузки.

        Args:
            key: Версионированный ключ набора данных.

        Returns:
            Сохранённый маркер.

        Raises:
            SeedStateAlreadyExistsRepositoryError: Если маркер уже записан.
            SeedStateRepositoryError: Если сохранить маркер не удалось.
        """
        try:
            state = SeedState(key=key)
            self.db_session.add(state)
            await self.db_session.commit()
            await self.db_session.refresh(state)
            return state
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) == "seed_state_pkey":
                logger.warning("⚠️ Маркер загрузки %s уже существует.", key)
                raise SeedStateAlreadyExistsRepositoryError(key=key) from error
            logger.error(
                "❌ Ограничение БД не позволило сохранить маркер загрузки %s.",
                key,
                exc_info=True,
            )
            raise SeedStateRepositoryError(
                f"Ошибка ограничения БД при сохранении маркера загрузки {key}."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить маркер загрузки %s.", key, exc_info=True)
            raise SeedStateRepositoryError(f"Ошибка сохранения маркера загрузки {key}.") from error
