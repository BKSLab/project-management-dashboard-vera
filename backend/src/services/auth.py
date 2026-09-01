import logging

from src.core.settings import get_settings
from src.db.models.users import User
from src.exceptions.auth import (
    AuthServiceError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidInviteCodeError,
)
from src.exceptions.users import (
    UsernameAlreadyExistsRepositoryError,
    UsernameConflictError,
    UsersRepositoryError,
)
from src.repositories.users import UsersRepository
from src.schemas.users import UserSchema
from src.utils.security import hash_password, secrets_match, verify_password
from src.utils.tokens import create_access_token

logger = logging.getLogger(__name__)


class AuthService:
    """Сервис регистрации и входа."""

    def __init__(self, users_repository: UsersRepository):
        self.users_repository = users_repository

    async def register(self, data: dict) -> UserSchema:
        """Регистрирует пользователя после проверки кода приглашения.

        Args:
            data: Поля регистрации, включая пароль и код приглашения.

        Returns:
            Карточка созданного пользователя.

        Raises:
            InvalidInviteCodeError: Если код приглашения не подошёл.
            UsernameConflictError: Если логин уже занят.
            AuthServiceError: Если создать пользователя не удалось.
        """
        payload = dict(data)
        invite_code = str(payload.pop("invite_code", ""))
        password = str(payload.pop("password", ""))
        payload.pop("password_confirm", None)

        expected_code = get_settings().auth.registration_invite_code.get_secret_value()
        if not secrets_match(invite_code, expected_code):
            logger.warning("⚠️ Регистрация с неверным кодом приглашения.")
            raise InvalidInviteCodeError()

        try:
            user = await self.users_repository.save(
                data={**payload, "password_hash": hash_password(password)}
            )
            logger.info("✅ Зарегистрирован пользователь %s.", user.username)
            return to_user_schema(user)
        except UsernameAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Логин %s уже занят.", error.username)
            raise UsernameConflictError(username=error.username) from error
        except UsersRepositoryError as error:
            logger.error("❌ Ошибка регистрации пользователя.", exc_info=True)
            raise AuthServiceError(str(error)) from error

    async def login(self, username: str, password: str) -> tuple[UserSchema, str]:
        """Проверяет пару логин и пароль и выпускает токен сессии.

        Args:
            username: Логин пользователя.
            password: Пароль в открытом виде.

        Returns:
            Карточка пользователя и подписанный токен сессии.

        Raises:
            InvalidCredentialsError: Если логин не найден или пароль неверен.
            InactiveUserError: Если учётная запись отключена.
            AuthServiceError: Если выполнить вход не удалось.
        """
        try:
            user = await self.users_repository.get_by_username(username=username)
            # Ответ одинаков для отсутствующего логина и неверного пароля,
            # иначе существующие логины можно перебрать по коду ответа.
            if user is None or not verify_password(password, user.password_hash):
                raise InvalidCredentialsError(username=username)
            if not user.is_active:
                raise InactiveUserError(user_id=user.id)

            logger.info("✅ Вход пользователя %s.", user.username)
            return to_user_schema(user), create_access_token(user_id=user.id)
        except (InvalidCredentialsError, InactiveUserError):
            raise
        except UsersRepositoryError as error:
            logger.error("❌ Ошибка входа пользователя.", exc_info=True)
            raise AuthServiceError(str(error)) from error


def to_user_schema(user: User) -> UserSchema:
    """Преобразует ORM-пользователя в схему ответа без чувствительных полей."""
    return UserSchema(
        id=user.id,
        username=user.username,
        last_name=user.last_name,
        first_name=user.first_name,
        middle_name=user.middle_name,
        email=user.email,
        phone=user.phone,
        telegram=user.telegram,
        has_avatar=user.avatar_key is not None,
        created_at=user.created_at,
    )
