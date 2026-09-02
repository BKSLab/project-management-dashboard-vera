"""Проверки инструментов записи MCP."""

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from src.db.models.api_tokens import ApiTokenScope
from src.db.models.project_members import ProjectMember, ProjectRole
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project, ProjectStatus
from src.db.models.tasks import Task, TaskPriority
from src.db.models.users import User
from src.dependencies.auth import AuthenticatedPrincipal
from src.exceptions.tasks import TaskNotFoundError
from src.mcp_server import context as ctx
from src.mcp_server import write_tools as wt
from src.mcp_server.context import READ_ONLY_TOKEN, ToolContext

PROJECT = Project(
    id=1,
    owner_id=1,
    key="VERA",
    name="Агент Вера",
    color="#58a6ff",
    status=ProjectStatus.ACTIVE,
)
STAGES = [
    ProjectStage(id=1, project_id=1, name="В работе", is_done_stage=False, order_index=0),
    ProjectStage(id=2, project_id=1, name="Готово", is_done_stage=True, order_index=1),
]
TASK = Task(id=10, project_id=1, stage_id=1, number=142, title="Настроить вход")


class FakeContext:
    """Контекст вызова MCP с заголовком токена."""

    headers = {"Authorization": "Bearer vera_test"}


class FakeTasksService:
    """Сервис задач, записывающий полученные вызовы."""

    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.created: dict | None = None
        self.updated: dict | None = None
        self.moved: dict | None = None
        self.deleted: int | None = None

    async def create_task(self, *, project_id: int, data: dict):
        if self.error:
            raise self.error
        self.created = {"project_id": project_id, **data}
        return type("T", (), {"key": "VERA-143", "title": data["title"]})()

    async def update_task(self, *, task_id: int, data: dict):
        if self.error:
            raise self.error
        self.updated = {"task_id": task_id, **data}
        return type("T", (), {"key": "VERA-142"})()

    async def move_task(self, *, task_id: int, stage_id: int):
        if self.error:
            raise self.error
        self.moved = {"task_id": task_id, "stage_id": stage_id}
        return type("T", (), {"key": "VERA-142"})()

    async def delete_task(self, *, task_id: int) -> None:
        if self.error:
            raise self.error
        self.deleted = task_id


class FakeCommentsService:
    """Сервис комментариев, записывающий полученные вызовы."""

    def __init__(self):
        self.added: dict | None = None

    async def add_comment(self, *, task_id: int, author_name: str | None, body_md: str):
        self.added = {"task_id": task_id, "author_name": author_name, "body_md": body_md}
        return type(
            "C",
            (),
            {"author_name": author_name, "created_at": datetime.now(UTC)},
        )()


def _tools(scope: ApiTokenScope = ApiTokenScope.WRITE) -> ToolContext:
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
    """Подменяет контекст, репозитории и доменные сервисы."""
    tasks_service = FakeTasksService()
    comments_service = FakeCommentsService()

    @asynccontextmanager
    async def fake_tool_context(context, *, require_write: bool = False):
        tools = _tools()
        if require_write and tools.principal.scope is not ApiTokenScope.WRITE:
            raise ToolError(READ_ONLY_TOKEN)
        yield tools

    class Projects:
        def __init__(self, session):
            pass

        async def get_by_key(self, key: str) -> Project | None:
            return PROJECT if key == "VERA" else None

    class Members:
        def __init__(self, session):
            pass

        async def get(self, *, project_id: int, user_id: int) -> ProjectMember:
            return ProjectMember(project_id=project_id, user_id=user_id, role=ProjectRole.OWNER)

    class Tasks:
        def __init__(self, session):
            pass

        async def get_by_project(self, project_id: int, **kwargs) -> list[Task]:
            return [TASK]

    class Stages:
        def __init__(self, session):
            pass

        async def get_by_project(self, project_id: int) -> list[ProjectStage]:
            return STAGES

    monkeypatch.setattr(wt, "tool_context", fake_tool_context)
    monkeypatch.setattr(wt, "ProjectStagesRepository", Stages)
    monkeypatch.setattr(wt, "build_tasks_service", lambda session: tasks_service)
    monkeypatch.setattr(wt, "build_comments_service", lambda session: comments_service)
    monkeypatch.setattr(ctx, "ProjectsRepository", Projects)
    monkeypatch.setattr(ctx, "ProjectMembersRepository", Members)
    monkeypatch.setattr(ctx, "TasksRepository", Tasks)
    return tasks_service, comments_service


async def test_create_task_passes_only_given_fields(tracker) -> None:
    """Непереданные поля не попадают в payload и не перетирают умолчания."""
    tasks_service, _ = tracker

    result = await wt.create_task(FakeContext(), project_key="VERA", title="  Новая  ")

    assert result["created"] is True
    assert tasks_service.created == {"project_id": 1, "title": "Новая"}


async def test_create_task_resolves_stage_by_name(tracker) -> None:
    """Стадия задаётся названием, а не числовым идентификатором."""
    tasks_service, _ = tracker

    await wt.create_task(FakeContext(), project_key="VERA", title="Новая", stage="готово")

    assert tasks_service.created["stage_id"] == 2


async def test_create_task_parses_priority_and_date(tracker) -> None:
    """Приоритет и срок приводятся к доменным типам."""
    tasks_service, _ = tracker

    await wt.create_task(
        FakeContext(),
        project_key="VERA",
        title="Новая",
        priority="high",
        due_date="2026-10-01",
    )

    assert tasks_service.created["priority"] is TaskPriority.HIGH
    assert tasks_service.created["due_date"] == date(2026, 10, 1)


async def test_create_task_rejects_unknown_priority(tracker) -> None:
    """Неизвестный приоритет подсказывает допустимые значения."""
    with pytest.raises(ToolError) as error:
        await wt.create_task(FakeContext(), project_key="VERA", title="Новая", priority="СРОЧНО")

    assert "URGENT" in str(error.value)


async def test_create_task_rejects_bad_date(tracker) -> None:
    """Некорректная дата отклоняется до обращения к сервису."""
    tasks_service, _ = tracker

    with pytest.raises(ToolError):
        await wt.create_task(
            FakeContext(),
            project_key="VERA",
            title="Новая",
            due_date="01.10.2026",
        )

    assert tasks_service.created is None


async def test_create_task_rejects_foreign_project(tracker) -> None:
    """Задача не создаётся в недоступном проекте."""
    tasks_service, _ = tracker

    with pytest.raises(ToolError):
        await wt.create_task(FakeContext(), project_key="OTHER", title="Новая")

    assert tasks_service.created is None


async def test_update_task_without_fields_is_rejected(tracker) -> None:
    """Пустое изменение — ошибка, а не молчаливый успех."""
    tasks_service, _ = tracker

    with pytest.raises(ToolError):
        await wt.update_task(FakeContext(), task_key="VERA-142")

    assert tasks_service.updated is None


async def test_update_task_touches_only_given_fields(tracker) -> None:
    """Переданные поля меняются, остальные не входят в payload."""
    tasks_service, _ = tracker

    result = await wt.update_task(FakeContext(), task_key="VERA-142", title="Другое")

    assert tasks_service.updated == {"task_id": 10, "title": "Другое"}
    assert result["updated_fields"] == ["title"]


async def test_update_task_empty_assignee_clears_it(tracker) -> None:
    """Пустая строка снимает исполнителя, а не ставит пустое имя."""
    tasks_service, _ = tracker

    await wt.update_task(FakeContext(), task_key="VERA-142", assignee="   ")

    assert tasks_service.updated["assignee"] is None


async def test_update_task_empty_due_date_clears_it(tracker) -> None:
    """Пустая строка снимает срок."""
    tasks_service, _ = tracker

    await wt.update_task(FakeContext(), task_key="VERA-142", due_date="")

    assert tasks_service.updated["due_date"] is None


async def test_move_task_resolves_stage_and_reports_done(tracker) -> None:
    """Перевод в завершающую стадию сообщает об этом вызывающему."""
    tasks_service, _ = tracker

    result = await wt.move_task(FakeContext(), task_key="VERA-142", stage="Готово")

    assert tasks_service.moved == {"task_id": 10, "stage_id": 2}
    assert result["is_done"] is True


async def test_move_task_unknown_stage_lists_available(tracker) -> None:
    """Неизвестная стадия подсказывает доступные."""
    with pytest.raises(ToolError) as error:
        await wt.move_task(FakeContext(), task_key="VERA-142", stage="Неизвестная")

    assert "В работе" in str(error.value)


async def test_delete_task_requires_confirmation(tracker) -> None:
    """Без подтверждения удаление не выполняется."""
    tasks_service, _ = tracker

    with pytest.raises(ToolError) as error:
        await wt.delete_task(FakeContext(), task_key="VERA-142")

    assert "confirm" in str(error.value)
    assert tasks_service.deleted is None


async def test_delete_task_with_confirmation(tracker) -> None:
    """С подтверждением задача удаляется."""
    tasks_service, _ = tracker

    result = await wt.delete_task(FakeContext(), task_key="VERA-142", confirm=True)

    assert tasks_service.deleted == 10
    assert result == {"task_key": "VERA-142", "deleted": True}


async def test_add_comment_defaults_author_to_token_owner(tracker) -> None:
    """Без подписи автором становится владелец токена."""
    _, comments_service = tracker

    await wt.add_comment(FakeContext(), task_key="VERA-142", body="Готово")

    assert comments_service.added["author_name"] == "Тестов Тест"


async def test_add_comment_uses_explicit_author(tracker) -> None:
    """Явная подпись имеет приоритет над владельцем токена."""
    _, comments_service = tracker

    await wt.add_comment(FakeContext(), task_key="VERA-142", body="Готово", author="Борис")

    assert comments_service.added["author_name"] == "Борис"


async def test_domain_error_is_translated(monkeypatch: pytest.MonkeyPatch, tracker) -> None:
    """Доменная ошибка отдаётся как понятная ошибка инструмента."""
    tasks_service, _ = tracker
    tasks_service.error = TaskNotFoundError(task_id=10)

    with pytest.raises(ToolError):
        await wt.update_task(FakeContext(), task_key="VERA-142", title="Другое")


async def test_read_scope_cannot_use_write_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Токен на чтение не допускается ни к одному изменяющему инструменту."""

    @asynccontextmanager
    async def read_only_context(context, *, require_write: bool = False):
        if require_write:
            raise ToolError(READ_ONLY_TOKEN)
        yield _tools(ApiTokenScope.READ)

    monkeypatch.setattr(wt, "tool_context", read_only_context)

    with pytest.raises(ToolError) as error:
        await wt.create_task(FakeContext(), project_key="VERA", title="Новая")
    assert str(error.value) == READ_ONLY_TOKEN

    with pytest.raises(ToolError):
        await wt.update_task(FakeContext(), task_key="VERA-142", title="Другое")
    with pytest.raises(ToolError):
        await wt.move_task(FakeContext(), task_key="VERA-142", stage="Готово")
    with pytest.raises(ToolError):
        await wt.delete_task(FakeContext(), task_key="VERA-142", confirm=True)
    with pytest.raises(ToolError):
        await wt.add_comment(FakeContext(), task_key="VERA-142", body="Текст")
