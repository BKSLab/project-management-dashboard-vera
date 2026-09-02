"""Проверки инструментов чтения MCP."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from src.db.models.api_tokens import ApiTokenScope
from src.db.models.project_members import ProjectMember, ProjectRole
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project, ProjectStatus
from src.db.models.task_comments import TaskComment
from src.db.models.tasks import Task, TaskPriority
from src.db.models.users import User
from src.dependencies.auth import AuthenticatedPrincipal
from src.mcp_server import server as srv
from src.mcp_server.context import ToolContext

VISIBLE = Project(
    id=1,
    owner_id=1,
    key="VERA",
    name="Агент Вера",
    color="#58a6ff",
    status=ProjectStatus.ACTIVE,
)
FOREIGN = Project(
    id=2,
    owner_id=99,
    key="OTHER",
    name="Чужой",
    color="#ff0000",
    status=ProjectStatus.ACTIVE,
)

STAGES = [
    ProjectStage(id=1, project_id=1, name="В работе", is_done_stage=False, order_index=0),
    ProjectStage(id=2, project_id=1, name="Готово", is_done_stage=True, order_index=1),
]
TASKS = [
    Task(
        id=10,
        project_id=1,
        stage_id=1,
        number=1,
        title="Настроить вход",
        description_md="Описание",
        priority=TaskPriority.HIGH,
        assignee="Борис",
    ),
    Task(
        id=11,
        project_id=1,
        stage_id=2,
        number=2,
        title="Сверстать дашборд",
        priority=TaskPriority.LOW,
        assignee="Анна",
    ),
]


class FakeContext:
    """Контекст вызова MCP с заголовком токена."""

    headers = {"Authorization": "Bearer vera_test"}


def _tools(scope: ApiTokenScope = ApiTokenScope.READ) -> ToolContext:
    return ToolContext(
        principal=AuthenticatedPrincipal(
            user=User(
                id=1,
                username="tester",
                password_hash="hash",
                last_name="Тестов",
                first_name="Тест",
                is_active=True,
            ),
            scope=scope,
            via_api_token=True,
        ),
        session=object(),
    )


@pytest.fixture
def tracker(monkeypatch: pytest.MonkeyPatch):
    """Подменяет репозитории и вход в контекст инструмента."""

    @asynccontextmanager
    async def fake_tool_context(context, *, require_write: bool = False):
        yield _tools()

    class Projects:
        def __init__(self, session):
            pass

        async def get_all(self) -> list[Project]:
            return [VISIBLE, FOREIGN]

        async def get_by_key(self, key: str) -> Project | None:
            return {"VERA": VISIBLE, "OTHER": FOREIGN}.get(key)

    class Members:
        def __init__(self, session):
            pass

        async def get_project_ids_for_user(self, user_id: int) -> set[int]:
            return {VISIBLE.id}

        async def get(self, *, project_id: int, user_id: int) -> ProjectMember | None:
            if project_id != VISIBLE.id:
                return None
            return ProjectMember(project_id=project_id, user_id=user_id, role=ProjectRole.OWNER)

    class Stages:
        def __init__(self, session):
            pass

        async def get_by_project(self, project_id: int) -> list[ProjectStage]:
            return STAGES

    class Tasks:
        def __init__(self, session):
            pass

        async def get_by_project(self, project_id: int, task_ids=None, **kwargs) -> list[Task]:
            if task_ids is None:
                return TASKS
            return [task for task in TASKS if task.id in task_ids]

        async def search_ids(self, project_id: int, search: str) -> set[int]:
            return {10} if "вход" in search else set()

    class Comments:
        def __init__(self, session):
            pass

        async def get_for_task(self, task_id: int) -> list[TaskComment]:
            return [
                TaskComment(
                    id=1,
                    task_id=task_id,
                    author_name="Борис",
                    body_md="Ждём уточнения",
                    created_at=datetime.now(UTC),
                )
            ]

    monkeypatch.setattr(srv, "tool_context", fake_tool_context)
    for module in (srv, __import__("src.mcp_server.context", fromlist=["x"])):
        monkeypatch.setattr(module, "ProjectsRepository", Projects, raising=False)
        monkeypatch.setattr(module, "ProjectMembersRepository", Members, raising=False)
        monkeypatch.setattr(module, "TasksRepository", Tasks, raising=False)
    monkeypatch.setattr(srv, "ProjectStagesRepository", Stages)
    monkeypatch.setattr(srv, "TaskCommentsRepository", Comments)


async def test_list_projects_hides_foreign_projects(tracker) -> None:
    """Проект, в котором пользователь не состоит, в списке не появляется."""
    result = await srv.list_projects(FakeContext())

    assert [item["project_key"] for item in result] == ["VERA"]


async def test_get_project_returns_stages_with_counts(tracker) -> None:
    """Карточка проекта содержит стадии и число задач в каждой."""
    result = await srv.get_project(FakeContext(), project_key="VERA")

    assert result["project_key"] == "VERA"
    assert result["total_tasks"] == 2
    assert {stage["name"]: stage["task_count"] for stage in result["stages"]} == {
        "В работе": 1,
        "Готово": 1,
    }


async def test_get_project_rejects_foreign_project(tracker) -> None:
    """Чужой проект недоступен даже при точном ключе."""
    with pytest.raises(ToolError):
        await srv.get_project(FakeContext(), project_key="OTHER")


async def test_list_tasks_returns_display_keys(tracker) -> None:
    """Наружу отдаются ключи вида VERA-1, а не числовые идентификаторы."""
    result = await srv.list_tasks(FakeContext(), project_key="VERA")

    assert [item["task_key"] for item in result] == ["VERA-1", "VERA-2"]
    assert all("id" not in item for item in result)


async def test_list_tasks_filters_by_stage(tracker) -> None:
    """Фильтр по названию стадии работает без учёта регистра."""
    result = await srv.list_tasks(FakeContext(), project_key="VERA", stage="в работе")

    assert [item["task_key"] for item in result] == ["VERA-1"]


async def test_list_tasks_unknown_stage_lists_available(tracker) -> None:
    """Неизвестная стадия подсказывает доступные, а не молча отдаёт пустоту."""
    with pytest.raises(ToolError) as error:
        await srv.list_tasks(FakeContext(), project_key="VERA", stage="Неизвестная")

    assert "В работе" in str(error.value)


async def test_list_tasks_filters_by_assignee(tracker) -> None:
    """Фильтр по исполнителю сравнивает без учёта регистра."""
    result = await srv.list_tasks(FakeContext(), project_key="VERA", assignee="анна")

    assert [item["task_key"] for item in result] == ["VERA-2"]


async def test_list_tasks_only_open_drops_done_stage(tracker) -> None:
    """Флаг только незавершённых отбрасывает задачи завершающей стадии."""
    result = await srv.list_tasks(FakeContext(), project_key="VERA", only_open=True)

    assert [item["task_key"] for item in result] == ["VERA-1"]


async def test_list_tasks_respects_limit(tracker) -> None:
    """Лимит ограничивает выдачу: агент не вытянет проект целиком случайно."""
    result = await srv.list_tasks(FakeContext(), project_key="VERA", limit=1)

    assert len(result) == 1


async def test_get_task_returns_details_and_comment_count(tracker) -> None:
    """Карточка задачи содержит описание и число комментариев."""
    result = await srv.get_task(FakeContext(), task_key="VERA-1")

    assert result["task_key"] == "VERA-1"
    assert result["description"] == "Описание"
    assert result["comment_count"] == 1
    assert result["is_done"] is False


async def test_get_task_marks_done_stage(tracker) -> None:
    """Завершённость берётся из признака стадии, а не из поля задачи."""
    result = await srv.get_task(FakeContext(), task_key="VERA-2")

    assert result["is_done"] is True


async def test_list_comments_returns_body_and_author(tracker) -> None:
    """Комментарии отдаются с автором и ключом задачи."""
    result = await srv.list_comments(FakeContext(), task_key="VERA-1")

    assert result[0]["task_key"] == "VERA-1"
    assert result[0]["author"] == "Борис"
    assert result[0]["body"] == "Ждём уточнения"


async def test_search_tasks_finds_by_text(tracker) -> None:
    """Лексический поиск возвращает совпавшие задачи."""
    result = await srv.search_tasks(FakeContext(), project_key="VERA", query="вход")

    assert [item["task_key"] for item in result] == ["VERA-1"]


async def test_search_tasks_returns_empty_without_matches(tracker) -> None:
    """Отсутствие совпадений — пустой список, а не ошибка."""
    result = await srv.search_tasks(FakeContext(), project_key="VERA", query="ничего")

    assert result == []


async def test_search_tasks_rejects_foreign_project(tracker) -> None:
    """Поиск не выполняется в недоступном проекте."""
    with pytest.raises(ToolError):
        await srv.search_tasks(FakeContext(), project_key="OTHER", query="вход")
