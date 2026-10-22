"""Выпуск и распознавание сервисных API-ключей .

Формат ключа: ``ttk_<prefix>_<secret>``:

- ``prefix`` — 8 случайных hex-символов, по ним ключ узнают в списке;
- ``secret`` — 32 случайных hex-символа (128 бит).

В базе хранится SHA-256 всего ключа. Медленная функция не нужна: энтропии
ключа хватает, чтобы перебор был бессмысленным, а проверка идёт на каждый
запрос агента.

Личные токены людей начинаются с ``tt_`` — после третьего символа у них
подчёркивание, поэтому с ``ttk_`` они не путаются никогда.
"""

import hashlib
import hmac
import secrets

API_KEY_MARKER = "ttk"
API_KEY_PREFIX = f"{API_KEY_MARKER}_"
_PREFIX_HEX = 8
_SECRET_HEX = 32


def generate_api_key() -> tuple[str, str]:
    """Выпускает новый ключ.

    Returns:
        Пара ``(raw_key, key_prefix)``: полный ключ показывается один раз,
        префикс хранится для узнавания в списке.
    """
    prefix_part = secrets.token_hex(_PREFIX_HEX // 2)
    secret_part = secrets.token_hex(_SECRET_HEX // 2)
    return (
        f"{API_KEY_PREFIX}{prefix_part}_{secret_part}",
        f"{API_KEY_PREFIX}{prefix_part}",
    )


def hash_api_key(raw_key: str) -> str:
    """Возвращает SHA-256 ключа в шестнадцатеричном виде."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Сверяет ключ с сохранённым хешем за постоянное время."""
    return hmac.compare_digest(hash_api_key(raw_key), key_hash)


def is_service_key(secret: str | None) -> bool:
    """Отличает сервисный ключ от личного токена по префиксу."""
    return bool(secret) and secret.startswith(API_KEY_PREFIX)


def key_prefix_of(raw_key: str) -> str | None:
    """Достаёт публичный префикс из предъявленного ключа.

    Returns:
        ``ttk_<prefix>`` либо ``None``, если ключ не того формата.
    """
    parts = raw_key.split("_", 2)
    if len(parts) != 3 or parts[0] != API_KEY_MARKER or len(parts[1]) != _PREFIX_HEX:
        return None
    return f"{parts[0]}_{parts[1]}"
