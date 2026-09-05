"""Проверки аутентификации и разрешения сущностей в MCP-инструментах."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from src.clients.vision import DisabledVisionCapability
from src.core.settings import get_settings
from src.db.models.api_tokens import ApiTokenScope
from src.db.models.project_members import ProjectMember, ProjectRole
from src.db.models.projects import Project
from src.db.models.tasks import Task
from src.db.models.users import User
from src.dependencies.auth import AuthenticatedPrincipal
from src.mcp_server import context as ctx
from src.mcp_server.context import ToolContext, _authorization_header, resolve_project, resolve_task


class FakeContext:
    """Контекст вызова MCP с подменёнными заголовками транспорта."""

    def __init__(self, headers: dict[str, str] | None):
        self.headers = headers


def _user() -> User:
    return User(
        id=1,
        username="tester",
        password_hash="hash",
        last_name="Тестов",
        first_name="Тест",
        is_active=True,
    )


def _project(**overrides) -> Project:
    values = {"id": 1, "owner_id": 1, "key": "PROJ", "name": "Тестовый проект", "color": "#58a6ff"}
    values.update(overrides)
    return Project(**values)


def _runtime() -> SimpleNamespace:
    """Контейнер клиентов, который в проде создаёт lifespan приложения."""
    return SimpleNamespace(
        embedding_client=AsyncMock(),
        qdrant_client=AsyncMock(),
        llm_client=AsyncMock(),
        vision=DisabledVisionCapability(),
    )


def _tools() -> ToolContext:
    return ToolContext(
        principal=AuthenticatedPrincipal(
            user=_user(),
            scope=ApiTokenScope.READ,
            via_api_token=True,
        ),
        session=object(),
        runtime=_runtime(),
        settings=get_settings(),
    )


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Authorization": "Bearer tt_x"}, "Bearer tt_x"),
        ({"authorization": "Bearer tt_x"}, "Bearer tt_x"),
        ({"AUTHORIZATION": "Bearer tt_x"}, "Bearer tt_x"),
        ({"X-Other": "нет"}, None),
        ({}, None),
        (None, None),
    ],
)
def test_authorization_header_is_case_insensitive(
    headers: dict[str, str] | None,
    expected: str | None,
) -> None:
    """Заголовок ищется без учёта регистра: транспорты нормализуют по-разному."""
    assert _authorization_header(FakeContext(headers)) == expected


async def test_resolve_project_rejects_foreign_project(monkeypatch: pytest.MonkeyPatch) -> None:
    """Чужой проект неотличим от несуществующего."""

    class Projects:
        def __init__(self, session):
            pass

        async def get_by_key(self, key: str) -> Project:
            return _project()

    class Members:
        def __init__(self, session):
            pass

        async def get(self, *, project_id: int, user_id: int) -> None:
            return None

    monkeypatch.setattr(ctx, "ProjectsRepository", Projects)
    monkeypatch.setattr(ctx, "ProjectMembersRepository", Members)

    with pytest.raises(ToolError) as error:
        await resolve_project(_tools(), "PROJ")

    assert str(error.value) == ctx.PROJECT_NOT_AVAILABLE


async def test_resolve_project_missing_project_gives_same_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Несуществующий проект отдаёт ту же формулировку, что и чужой."""

    class Projects:
        def __init__(self, session):
            pass

        async def get_by_key(self, key: str) -> None:
            return None

    monkeypatch.setattr(ctx, "ProjectsRepository", Projects)

    with pytest.raises(ToolError) as error:
        await resolve_project(_tools(), "OTHER")

    assert str(error.value) == ctx.PROJECT_NOT_AVAILABLE


async def test_resolve_project_allows_member(monkeypatch: pytest.MonkeyPatch) -> None:
    """Участник проекта получает его карточку."""

    class Projects:
        def __init__(self, session):
            pass

        async def get_by_key(self, key: str) -> Project:
            return _project()

    class Members:
        def __init__(self, session):
            pass

        async def get(self, *, project_id: int, user_id: int) -> ProjectMember:
            return ProjectMember(project_id=project_id, user_id=user_id, role=ProjectRole.OWNER)

    monkeypatch.setattr(ctx, "ProjectsRepository", Projects)
    monkeypatch.setattr(ctx, "ProjectMembersRepository", Members)

    project = await resolve_project(_tools(), "proj")

    assert project.key == "PROJ"


@pytest.mark.parametrize("value", ["", "   ", "PROJ", "PROJ-", "PROJ-abc", "-142", "142"])
async def test_resolve_task_rejects_malformed_key(value: str) -> None:
    """Некорректный ключ задачи отклоняется до обращения к базе."""
    with pytest.raises(ToolError):
        await resolve_task(_tools(), value)


async def test_resolve_task_rejects_unknown_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Несуществующий номер задачи в доступном проекте даёт отказ."""

    class Projects:
        def __init__(self, session):
            pass

        async def get_by_key(self, key: str) -> Project:
            return _project()

    class Members:
        def __init__(self, session):
            pass

        async def get(self, *, project_id: int, user_id: int) -> ProjectMember:
            return ProjectMember(project_id=project_id, user_id=user_id, role=ProjectRole.OWNER)

    class Tasks:
        def __init__(self, session):
            pass

        async def get_by_project(self, project_id: int) -> list[Task]:
            return [Task(id=1, project_id=project_id, stage_id=1, number=1, title="Есть")]

    monkeypatch.setattr(ctx, "ProjectsRepository", Projects)
    monkeypatch.setattr(ctx, "ProjectMembersRepository", Members)
    monkeypatch.setattr(ctx, "TasksRepository", Tasks)

    with pytest.raises(ToolError) as error:
        await resolve_task(_tools(), "PROJ-999")

    assert str(error.value) == ctx.TASK_NOT_AVAILABLE


async def test_resolve_task_checks_project_access_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """Задача чужого проекта не проверяется по номеру: доступ отсекается раньше."""
    touched: list[str] = []

    class Projects:
        def __init__(self, session):
            pass

        async def get_by_key(self, key: str) -> Project:
            return _project()

    class Members:
        def __init__(self, session):
            pass

        async def get(self, *, project_id: int, user_id: int) -> None:
            return None

    class Tasks:
        def __init__(self, session):
            pass

        async def get_by_project(self, project_id: int) -> list[Task]:
            touched.append("tasks")
            return []

    monkeypatch.setattr(ctx, "ProjectsRepository", Projects)
    monkeypatch.setattr(ctx, "ProjectMembersRepository", Members)
    monkeypatch.setattr(ctx, "TasksRepository", Tasks)

    with pytest.raises(ToolError) as error:
        await resolve_task(_tools(), "PROJ-1")

    assert str(error.value) == ctx.PROJECT_NOT_AVAILABLE
    assert touched == []


def test_tool_context_exposes_user() -> None:
    """Инструмент получает пользователя, а не только принципала."""
    tools = _tools()

    assert tools.user.id == 1
    assert tools.principal.via_api_token is True
    assert isinstance(datetime.now(UTC), datetime)
