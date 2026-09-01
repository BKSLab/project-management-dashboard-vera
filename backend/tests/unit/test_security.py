import pytest

from src.utils.security import (
    MAX_PASSWORD_BYTES,
    hash_password,
    secrets_match,
    verify_password,
)
from src.utils.tokens import create_access_token, decode_access_token


def test_hash_is_salted_and_verifiable() -> None:
    first = hash_password("pa$$word123")
    second = hash_password("pa$$word123")

    # Разная соль на каждый вызов: одинаковые пароли не должны давать одинаковый хеш.
    assert first != second
    assert verify_password("pa$$word123", first)
    assert verify_password("pa$$word123", second)


def test_wrong_password_is_rejected() -> None:
    assert not verify_password("другой", hash_password("pa$$word123"))


def test_broken_hash_does_not_raise() -> None:
    # Испорченная запись в БД — это неудачный вход, а не падение сервера.
    assert not verify_password("pa$$word123", "не хеш")


def test_long_password_is_truncated_predictably() -> None:
    password = "a" * (MAX_PASSWORD_BYTES + 20)

    assert verify_password(password, hash_password(password))


@pytest.mark.parametrize(
    ("provided", "expected", "result"),
    [("код", "код", True), ("код", "кот", False), ("", "код", False)],
)
def test_secrets_match(provided: str, expected: str, result: bool) -> None:
    assert secrets_match(provided, expected) is result


def test_token_roundtrip() -> None:
    assert decode_access_token(create_access_token(user_id=42)) == 42


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(user_id=42)
    tampered = f"{token[:-3]}abc"

    assert decode_access_token(tampered) is None
    assert decode_access_token("совсем не токен") is None
    assert decode_access_token("") is None
