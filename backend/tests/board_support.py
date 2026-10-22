"""Local account fixtures for the board domain regression suite."""

from src.db.models.users import User


def local_user(*, username: str, display_name: str, **fields) -> User:
    parts = display_name.split(maxsplit=1)
    return User(
        username=username,
        password_hash="test-hash",
        last_name=parts[0],
        first_name=parts[1] if len(parts) > 1 else "Test",
        **fields,
    )


def user_display_name(user: User) -> str:
    return " ".join(part for part in (user.last_name, user.first_name, user.middle_name) if part)
