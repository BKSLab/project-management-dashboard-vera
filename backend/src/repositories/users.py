import logging

from sqlalchemy import Result, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.users import User
from src.exceptions.users import (
    UsernameAlreadyExistsRepositoryError,
    UsersRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name

logger = logging.getLogger(__name__)

USERNAME_CONSTRAINTS = frozenset({"users_username_key", "ix_users_username"})


class UsersRepository:
    """Репозиторий пользователей."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_id(self, user_id: int) -> User | None:
        """Возвращает пользователя по идентификатору.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Найденный пользователь или ``None``.

        Raises:
            UsersRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить пользователя id=%s.", user_id, exc_info=True)
            raise UsersRepositoryError(f"Ошибка получения пользователя id={user_id}.") from error

    async def get_by_username(self, username: str) -> User | None:
        """Возвращает пользователя по логину без учёта регистра.

        Args:
            username: Логин пользователя.

        Returns:
            Найденный пользователь или ``None``.

        Raises:
            UsersRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(User).where(func.lower(User.username) == username.lower())
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить пользователя по логину.", exc_info=True)
            raise UsersRepositoryError("Ошибка получения пользователя по логину.") from error

    async def count(self) -> int:
        """Возвращает количество зарегистрированных пользователей.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Количество пользователей.

        Raises:
            UsersRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(select(func.count()).select_from(User))
            return int(result.scalar_one())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подсчитать пользователей.", exc_info=True)
            raise UsersRepositoryError("Ошибка подсчёта пользователей.") from error

    async def save(self, data: dict) -> User:
        """Создаёт пользователя и возвращает сохранённую модель.

        Args:
            data: Поля нового пользователя.

        Returns:
            Сохранённый пользователь.

        Raises:
            UsernameAlreadyExistsRepositoryError: Если логин уже занят.
            UsersRepositoryError: Если сохранить пользователя не удалось.
        """
        try:
            user = User(**data)
            self.db_session.add(user)
            await self.db_session.commit()
            await self.db_session.refresh(user)
            return user
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) in USERNAME_CONSTRAINTS:
                username = str(data.get("username", ""))
                logger.warning("⚠️ Логин %s уже занят.", username)
                raise UsernameAlreadyExistsRepositoryError(username=username) from error
            logger.error("❌ Ограничение БД не позволило создать пользователя.", exc_info=True)
            raise UsersRepositoryError(
                "Ошибка ограничения БД при создании пользователя."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось создать пользователя.", exc_info=True)
            raise UsersRepositoryError("Ошибка создания пользователя.") from error

    async def update(self, user: User, data: dict) -> User:
        """Обновляет пользователя и возвращает сохранённую модель.

        Args:
            user: Изменяемая ORM-модель пользователя.
            data: Новые значения полей.

        Returns:
            Обновлённый пользователь.

        Raises:
            UsersRepositoryError: Если обновить пользователя не удалось.
        """
        try:
            for field, value in data.items():
                setattr(user, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(user)
            return user
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить пользователя id=%s.", user.id, exc_info=True)
            raise UsersRepositoryError(f"Ошибка обновления пользователя id={user.id}.") from error
