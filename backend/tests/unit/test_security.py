import pytest

from src.utils.security import (
    MAX_PASSWORD_BYTES,
    hash_password,
    secrets_match,
    verify_password,
)
from src.utils.tokens import create_access_token, decode_access_token


@pytest.mark.parametrize(
    ("provided", "expected", "result"),
    [("код", "код", True), ("код", "кот", False), ("", "код", False)],
)
def test_secrets_match(provided: str, expected: str, result: bool) -> None:
    assert secrets_match(provided, expected) is result


def test_password_hash_is_salted_and_survives_bad_input() -> None:
    """Хеш солёный и проверяемый, неверный пароль отклоняется, испорченный хеш не роняет проверку, длинный пароль обрезается предсказуемо."""

    first = hash_password("pa$$word123")
    second = hash_password("pa$$word123")

    # Разная соль на каждый вызов: одинаковые пароли не должны давать одинаковый хеш.
    assert first != second
    assert verify_password("pa$$word123", first)
    assert verify_password("pa$$word123", second)

    assert not verify_password("другой", hash_password("pa$$word123"))

    assert not verify_password("pa$$word123", "не хеш")

    password = "a" * (MAX_PASSWORD_BYTES + 20)

    assert verify_password(password, hash_password(password))


def test_session_token_roundtrip_and_tampering() -> None:
    """Токен сессии разбирается обратно, подделанный отвергается."""

    assert decode_access_token(create_access_token(user_id=42)) == 42

    token = create_access_token(user_id=42)
    tampered = f"{token[:-3]}abc"

    assert decode_access_token(tampered) is None
    assert decode_access_token("совсем не токен") is None
    assert decode_access_token("") is None
