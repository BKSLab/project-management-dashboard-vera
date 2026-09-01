"""Выпуск и разбор JWT сессии."""

import logging
from datetime import UTC, datetime, timedelta

import jwt

from src.core.settings import get_settings

logger = logging.getLogger(__name__)


def create_access_token(user_id: int) -> str:
    """Выпускает токен сессии для пользователя.

    Args:
        user_id: Идентификатор пользователя.

    Returns:
        Подписанный JWT.
    """
    settings = get_settings().auth
    issued_at = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(hours=settings.access_token_ttl_hours),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> int | None:
    """Проверяет подпись и срок токена и возвращает идентификатор пользователя.

    Args:
        token: Значение JWT из cookie.

    Returns:
        Идентификатор пользователя или ``None``, если токен недействителен.
    """
    settings = get_settings().auth
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        logger.info("ℹ️ Токен сессии истёк.")
        return None
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        # Подделанный или испорченный токен — обычная ситуация, не ошибка сервера.
        logger.warning("⚠️ Получен недействительный токен сессии.")
        return None
