"""Выпуск и проверка секретов токенов внешних клиентов."""

import hashlib
import secrets

TOKEN_PREFIX = "vera_"
TOKEN_ENTROPY_BYTES = 32
DISPLAY_PREFIX_LENGTH = 8


def generate_token_secret() -> str:
    """Выпускает новый секрет токена.

    Returns:
        Секрет вида ``vera_<случайная часть>``, показываемый пользователю один раз.
    """
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)}"


def hash_token_secret(secret: str) -> str:
    """Считает хеш секрета для хранения и поиска.

    Секрет высокоэнтропийный, поэтому медленная функция здесь не нужна:
    перебор невозможен, а проверка выполняется на каждый запрос агента.

    Args:
        secret: Предъявленный секрет токена.

    Returns:
        SHA-256 в шестнадцатеричном виде.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def build_display_prefix(secret: str) -> str:
    """Возвращает часть секрета, по которой владелец узнаёт токен в списке.

    Args:
        secret: Секрет токена.

    Returns:
        Первые символы секрета без случайной части.
    """
    return secret[:DISPLAY_PREFIX_LENGTH]
