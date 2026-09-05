"""Разрешение принципала запроса сервисом аутентификации.

Правила прав живут в сервисе, а не в Depends-слое, поэтому проверяются
здесь — один раз для обоих транспортов.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.db.models.api_tokens import ApiToken, ApiTokenScope
from src.db.models.users import User
from src.exceptions.api_tokens import ApiTokensRepositoryError
from src.exceptions.auth import (
    AuthServiceError,
    InactiveUserError,
    NotAuthenticatedError,
)
from src.exceptions.users import UsersRepositoryError
from src.repositories.api_tokens import ApiTokensRepository
from src.repositories.users import UsersRepository
from src.services.auth import AuthService, Principal
from src.utils.api_tokens import hash_token_secret
from src.utils.tokens import create_access_token

SECRET = "tt_valid"
INVITE = "код-приглашения"


def make_user(**overrides) -> User:
    """Пользователь с заполненными полями идентичности."""
    values = {
        "id": 1,
        "username": "tester",
        "password_hash": "hash",
        "last_name": "Тестов",
        "first_name": "Тест",
        "middle_name": None,
        "is_active": True,
        "created_at": datetime.now(UTC),
    }
    values.update(overrides)
    return User(**values)


def make_token(secret: str = SECRET, **overrides) -> ApiToken:
    """Действующий токен доступа, если не указано иное."""
    now = datetime.now(UTC)
    values = {
        "id": 1,
        "user_id": 1,
        "name": "Ноутбук",
        "token_hash": hash_token_secret(secret),
        "prefix": secret[:8],
        "scope": ApiTokenScope.READ,
        "expires_at": None,
        "revoked_at": None,
        "last_used_at": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return ApiToken(**values)


def build_service(
    *,
    user: User | None = None,
    token: ApiToken | None = None,
    users_error: Exception | None = None,
    tokens_error: Exception | None = None,
) -> tuple[AuthService, AsyncMock, AsyncMock]:
    """Собирает сервис на дублёрах репозиториев с фиксированными ответами."""
    users = AsyncMock(spec=UsersRepository)
    users.get_by_id.return_value = user
    if users_error is not None:
        users.get_by_id.side_effect = users_error

    tokens = AsyncMock(spec=ApiTokensRepository)
    tokens.get_active_by_hash.return_value = token
    if tokens_error is not None:
        tokens.get_active_by_hash.side_effect = tokens_error

    service = AuthService(
        users_repository=users,
        tokens_repository=tokens,
        invite_code=INVITE,
    )
    return service, users, tokens


async def test_valid_token_authenticates_and_keeps_scope() -> None:
    """Действующий токен пускает пользователя и сохраняет свои права."""
    service, _, tokens = build_service(user=make_user(), token=make_token())

    principal = await service.resolve_principal(session_token=None, bearer_secret=SECRET)

    assert principal.user_id == 1
    assert principal.username == "tester"
    assert principal.scope is ApiTokenScope.READ
    assert principal.via_api_token is True
    assert principal.can_write is False
    tokens.touch_last_used.assert_awaited_once()


async def test_write_token_may_write() -> None:
    """Токен с правом записи разрешает изменяющие операции."""
    service, _, _ = build_service(
        user=make_user(),
        token=make_token(scope=ApiTokenScope.WRITE),
    )

    principal = await service.resolve_principal(session_token=None, bearer_secret=SECRET)

    assert principal.can_write is True


async def test_unknown_token_is_rejected() -> None:
    """Выдуманный токен не пускает."""
    service, _, _ = build_service(user=make_user(), token=None)

    with pytest.raises(NotAuthenticatedError):
        await service.resolve_principal(session_token=None, bearer_secret="tt_unknown")


async def test_token_of_disabled_user_is_rejected() -> None:
    """Отключённый пользователь не проходит даже с действующим токеном."""
    service, _, _ = build_service(user=make_user(is_active=False), token=make_token())

    with pytest.raises(InactiveUserError):
        await service.resolve_principal(session_token=None, bearer_secret=SECRET)


async def test_token_of_deleted_user_is_rejected() -> None:
    """Токен пережившего удаление пользователя не пускает."""
    service, _, _ = build_service(user=None, token=make_token())

    with pytest.raises(NotAuthenticatedError):
        await service.resolve_principal(session_token=None, bearer_secret=SECRET)


async def test_token_repository_failure_is_not_an_access_denial() -> None:
    """Сбой базы отличается от отказа в доступе.

    Иначе временная недоступность PostgreSQL молча выглядела бы как
    неверный токен, и причину искали бы не там.
    """
    service, _, _ = build_service(
        user=make_user(),
        tokens_error=ApiTokensRepositoryError("сбой БД"),
    )

    with pytest.raises(AuthServiceError) as error:
        await service.resolve_principal(session_token=None, bearer_secret=SECRET)

    assert not isinstance(error.value, NotAuthenticatedError)
    assert error.value.status_code == 500


async def test_users_repository_failure_is_not_an_access_denial() -> None:
    """Сбой чтения пользователя тоже не превращается в 401."""
    service, _, _ = build_service(
        token=make_token(),
        users_error=UsersRepositoryError("сбой БД"),
    )

    with pytest.raises(AuthServiceError) as error:
        await service.resolve_principal(session_token=None, bearer_secret=SECRET)

    assert not isinstance(error.value, NotAuthenticatedError)


async def test_failed_touch_does_not_block_access() -> None:
    """Отметка использования — диагностика, а не условие доступа."""
    service, _, tokens = build_service(user=make_user(), token=make_token())
    tokens.touch_last_used.side_effect = ApiTokensRepositoryError("сбой БД")

    principal = await service.resolve_principal(session_token=None, bearer_secret=SECRET)

    assert principal.user_id == 1


async def test_cookie_session_has_full_rights() -> None:
    """Вход по cookie имеет полные права: скоуп введён для внешних клиентов."""
    user = make_user()
    service, _, _ = build_service(user=user)

    principal = await service.resolve_principal(
        session_token=create_access_token(user.id),
        bearer_secret=None,
    )

    assert principal.scope is ApiTokenScope.WRITE
    assert principal.via_api_token is False
    assert principal.can_write is True


async def test_bearer_takes_precedence_over_cookie() -> None:
    """При обоих способах побеждает токен: иначе скоуп можно было бы обойти."""
    user = make_user()
    service, _, _ = build_service(user=user, token=make_token())

    principal = await service.resolve_principal(
        session_token=create_access_token(user.id),
        bearer_secret=SECRET,
    )

    assert principal.scope is ApiTokenScope.READ
    assert principal.via_api_token is True


async def test_no_credentials_at_all_is_rejected() -> None:
    """Без cookie и без заголовка доступа нет."""
    service, _, _ = build_service(user=make_user())

    with pytest.raises(NotAuthenticatedError):
        await service.resolve_principal(session_token=None, bearer_secret=None)


async def test_forged_cookie_is_rejected() -> None:
    """Подделанная cookie не проходит проверку подписи."""
    service, _, _ = build_service(user=make_user())

    with pytest.raises(NotAuthenticatedError):
        await service.resolve_principal(session_token="не.настоящий.токен", bearer_secret=None)


def test_principal_composes_names_for_each_consumer() -> None:
    """Полное и короткое имя различаются отчеством и берутся из принципала."""
    principal = Principal(
        user_id=1,
        username="tester",
        last_name="Тестов",
        first_name="Тест",
        middle_name="Тестович",
        scope=ApiTokenScope.WRITE,
        via_api_token=False,
    )

    assert principal.full_name == "Тестов Тест Тестович"
    assert principal.short_name == "Тестов Тест"


def test_principal_falls_back_to_username_without_name() -> None:
    """Без фамилии и имени подписью остаётся логин."""
    principal = Principal(
        user_id=1,
        username="tester",
        last_name="",
        first_name="",
        middle_name=None,
        scope=ApiTokenScope.READ,
        via_api_token=True,
    )

    assert principal.full_name == "tester"
    assert principal.short_name == "tester"


@pytest.mark.parametrize(
    "case",
    ["expired", "revoked"],
    ids=["истёкший", "отозванный"],
)
async def test_unusable_tokens_look_like_unknown(case: str) -> None:
    """Истёкший и отозванный токен неотличимы от выдуманного.

    Репозиторий не отдаёт недействующий токен, и сервис не должен пытаться
    объяснить клиенту, чем именно он плох.
    """
    service, _, _ = build_service(user=make_user(), token=None)

    with pytest.raises(NotAuthenticatedError):
        await service.resolve_principal(session_token=None, bearer_secret=SECRET)
