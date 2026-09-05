"""READ-токен против всех классов доменных мутаций.

Route-graph тест доказывает, что зависимость подключена. Этот — что она
действительно останавливает запрос: токен на чтение получает 403 и не
доходит до сервиса.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.db.models.api_tokens import ApiTokenScope
from src.dependencies.services import (
    get_project_agent_service,
    get_users_service,
    get_wbs_suggestion_service,
)
from src.schemas.knowledge import KnowledgeAnswerSchema
from src.schemas.wbs_suggestion import WbsSuggestionSchema
from src.services.project_agent import ProjectAgentService
from src.services.users import UsersService
from src.services.wbs_suggestion import WbsSuggestionService
from tests.api.bearer_doubles import auth_header, install_bearer_auth, user_schema

# По одному представителю каждого класса доменных мутаций.
MUTATION_SAMPLES = [
    ("PATCH", "/api/v1/users/me", {"json": {"first_name": "Новое"}}),
    ("POST", "/api/v1/users/me/password", {"json": {"current_password": "x", "new_password": "y"}}),
    ("DELETE", "/api/v1/users/me/avatar", {}),
    ("POST", "/api/v1/dashboard/analytics", {"json": {}}),
    ("POST", "/api/v1/projects", {"json": {"key": "NEW", "name": "Новый"}}),
    ("PATCH", "/api/v1/projects/1", {"json": {"name": "Другое"}}),
    ("DELETE", "/api/v1/projects/1", {}),
    ("POST", "/api/v1/projects/1/members", {"json": {"username": "someone"}}),
    ("DELETE", "/api/v1/projects/1/members/2", {}),
    ("POST", "/api/v1/projects/1/stages", {"json": {"name": "Стадия"}}),
    ("PATCH", "/api/v1/stages/1", {"json": {"name": "Другая"}}),
    ("DELETE", "/api/v1/stages/1", {}),
    ("POST", "/api/v1/projects/1/tasks", {"json": {"title": "Задача"}}),
    ("PATCH", "/api/v1/tasks/1", {"json": {"title": "Другая"}}),
    ("DELETE", "/api/v1/tasks/1", {}),
    ("PATCH", "/api/v1/tasks/1/move", {"json": {"stage_id": 1}}),
    ("POST", "/api/v1/tasks/1/baseline", {"json": {}}),
    ("POST", "/api/v1/tasks/1/comments", {"json": {"body_md": "Текст"}}),
    ("DELETE", "/api/v1/comments/1", {}),
    ("POST", "/api/v1/projects/1/wbs/nodes", {"json": {"title": "Раздел"}}),
    ("PATCH", "/api/v1/projects/1/wbs/nodes/1", {"json": {"title": "Другой"}}),
    ("DELETE", "/api/v1/projects/1/wbs/nodes/1", {}),
    ("POST", "/api/v1/projects/1/wbs/suggestion/apply", {"json": {"nodes": [], "placements": []}}),
    ("POST", "/api/v1/projects/1/documents", {"json": {"title": "Документ", "content_md": "x"}}),
    ("PATCH", "/api/v1/documents/1", {"json": {"title": "Другой"}}),
    ("DELETE", "/api/v1/documents/1", {}),
    ("POST", "/api/v1/document-links", {"json": {"document_id": 1, "task_id": 1}}),
    ("DELETE", "/api/v1/document-links/1", {}),
    ("POST", "/api/v1/projects/1/milestones", {"json": {"title": "Веха", "due_date": "2026-10-01"}}),
    ("PATCH", "/api/v1/projects/1/milestones/1", {"json": {"title": "Другая"}}),
    ("DELETE", "/api/v1/projects/1/milestones/1", {}),
    ("POST", "/api/v1/projects/1/task-dependencies", {"json": {"predecessor_id": 1, "successor_id": 2}}),
    ("DELETE", "/api/v1/projects/1/task-dependencies/1", {}),
    ("POST", "/api/v1/projects/1/board/stickers", {"json": {"body": "Текст"}}),
    ("PATCH", "/api/v1/projects/1/board/stickers/1", {"json": {"body": "Другой"}}),
    ("DELETE", "/api/v1/projects/1/board/stickers/1?revision=1", {}),
    ("POST", "/api/v1/projects/1/calendar/scenarios/apply", {"json": {"changes": []}}),
    ("POST", "/api/v1/projects/1/knowledge/reindex", {}),
    ("POST", "/api/v1/tasks/1/attachments", {"files": {"file": ("a.txt", b"x", "text/plain")}}),
    ("DELETE", "/api/v1/tasks/1/attachments/1", {}),
    (
        "POST",
        "/api/v1/tasks/1/documents/import",
        {"files": {"file": ("a.txt", b"x", "text/plain")}},
    ),
]

# Логически read-only POST: токену на чтение они доступны.
READ_ONLY_POST_SAMPLES = [
    ("/api/v1/projects/1/calendar/scenarios/preview", {"json": {"changes": []}}),
    ("/api/v1/projects/1/wbs/suggestion", {}),
    ("/api/v1/projects/1/knowledge/ask", {"json": {"question": "Что нового?", "history": []}}),
]


@pytest.fixture
def bearer_token(anonymous_app) -> callable:
    """Ставит в граф аутентификацию по токену с выбранными правами.

    Доменные сервисы подменяются заглушками: тест проверяет guard прав, а
    не поведение сценариев за ним.
    """

    def install(scope: ApiTokenScope) -> None:
        install_bearer_auth(scope)

        users_service = AsyncMock(spec=UsersService)
        users_service.get_user.return_value = user_schema()
        users_service.update_profile.return_value = user_schema()

        suggestion_service = AsyncMock(spec=WbsSuggestionService)
        suggestion_service.suggest.return_value = WbsSuggestionSchema()

        agent_service = AsyncMock(spec=ProjectAgentService)
        agent_service.ask.return_value = KnowledgeAnswerSchema(answer="Ответ", sources=[])

        app.dependency_overrides.update(
            {
                get_users_service: lambda: users_service,
                get_wbs_suggestion_service: lambda: suggestion_service,
                get_project_agent_service: lambda: agent_service,
            }
        )

    return install


@pytest.fixture
def anonymous_app():
    """Снимает автоподмену сессии: проверяется настоящая цепочка прав."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    MUTATION_SAMPLES,
    ids=[f"{method} {path}" for method, path, _ in MUTATION_SAMPLES],
)
async def test_read_token_cannot_mutate(
    api_client: AsyncClient,
    bearer_token,
    method: str,
    path: str,
    payload: dict,
) -> None:
    """Токен на чтение получает 403 на каждом классе доменных мутаций."""
    bearer_token(ApiTokenScope.READ)

    response = await api_client.request(
        method,
        path,
        headers=auth_header(),
        **payload,
    )

    assert response.status_code == 403, (
        f"{method} {path} доступен токену на чтение: {response.status_code}"
    )
    assert response.json() == {"detail": "Токен выдан только на чтение."}


@pytest.mark.parametrize(
    ("path", "payload"),
    READ_ONLY_POST_SAMPLES,
    ids=[path for path, _ in READ_ONLY_POST_SAMPLES],
)
async def test_read_token_passes_read_only_posts(
    api_client: AsyncClient,
    bearer_token,
    path: str,
    payload: dict,
) -> None:
    """Расчёт и предпросмотр остаются доступны токену на чтение.

    Проверяется именно отсутствие 403 от guard прав: дальше запрос может
    упасть по любой причине, и это уже не про права.
    """
    bearer_token(ApiTokenScope.READ)

    response = await api_client.post(
        path,
        headers=auth_header(),
        **payload,
    )

    assert response.status_code != 403, f"{path} закрыт для токена на чтение."


async def test_write_token_passes_the_scope_guard(
    api_client: AsyncClient,
    bearer_token,
) -> None:
    """Токен с правом записи проходит guard прав."""
    bearer_token(ApiTokenScope.WRITE)

    response = await api_client.patch(
        "/api/v1/users/me",
        headers=auth_header(),
        json={"first_name": "Новое"},
    )

    assert response.status_code != 403


async def test_read_token_still_reads(api_client: AsyncClient, bearer_token) -> None:
    """Токен на чтение не теряет доступ к чтению."""
    bearer_token(ApiTokenScope.READ)

    response = await api_client.get(
        "/api/v1/auth/me",
        headers=auth_header(),
    )

    assert response.status_code != 403
