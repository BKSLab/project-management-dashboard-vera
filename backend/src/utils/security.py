"""Хеширование паролей и безопасное сравнение секретов.

Используется `bcrypt` напрямую: `passlib` 1.7.4 несовместим с `bcrypt` 4.x
и на каждом хешировании пишет в лог трассировку чтения версии.
"""

import hmac

import bcrypt

# bcrypt обрезает вход на 72 байтах, поэтому длину ограничиваем явно
# и предсказуемо, а не молча теряем хвост пароля.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Возвращает bcrypt-хеш пароля.

    Args:
        password: Пароль в открытом виде.

    Returns:
        Хеш в виде строки, пригодной для хранения в БД.
    """
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль против хеша.

    Args:
        password: Пароль в открытом виде.
        password_hash: Сохранённый хеш.

    Returns:
        ``True``, если пароль подходит.
    """
    try:
        return bcrypt.checkpw(_encode(password), password_hash.encode("utf-8"))
    except ValueError:
        # Испорченный хеш не должен ронять вход — это просто неудачная попытка.
        return False


def secrets_match(provided: str, expected: str) -> bool:
    """Сравнивает секреты за постоянное время.

    Обычное сравнение строк завершается на первом различии, поэтому по времени
    ответа код приглашения можно подобрать посимвольно.

    Args:
        provided: Значение, пришедшее от пользователя.
        expected: Ожидаемое значение.

    Returns:
        ``True``, если значения совпадают.
    """
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _encode(password: str) -> bytes:
    """Приводит пароль к байтам в пределах, которые понимает bcrypt."""
    return password.encode("utf-8")[:MAX_PASSWORD_BYTES]
