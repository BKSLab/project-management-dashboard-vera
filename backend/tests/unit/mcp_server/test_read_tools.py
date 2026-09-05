"""Проверки инструментов чтения MCP."""

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from src.clients.vision import DisabledVisionCapability
from src.core.settings import get_settings
from src.db.models.api_tokens import ApiTokenScope
from src.db.models.project_members import ProjectMember, ProjectRole
from src.db.models.project_milestones import ProjectMilestoneStatus
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project, ProjectStatus
from src.db.models.task_comments import TaskComment
from src.db.models.tasks import Task, TaskPriority
from src.db.models.users import User
from src.dependencies.auth import AuthenticatedPrincipal
from src.mcp_server import server as srv
from src.mcp_server.context import ToolContext
from src.schemas.calendar import (
    CalendarMilestoneSchema,
    CalendarRangeSchema,
    CalendarRiskReasonSchema,
    CalendarSummarySchema,
    CalendarTaskSchema,
    UnscheduledTasksPageSchema,
)

VISIBLE = Project(
    id=1,
    owner_id=1,
    key="PROJ",
    name="Тестовый проект",
    color="#58a6ff",
    status=ProjectStatus.ACTIVE,
    due_date=date(2026, 9, 30),
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

    headers = {"Authorization": "Bearer tt_test"}


def _runtime() -> SimpleNamespace:
    """Контейнер клиентов, который в проде создаёт lifespan приложения."""
    return SimpleNamespace(
        embedding_client=AsyncMock(),
        qdrant_client=AsyncMock(),
        llm_client=AsyncMock(),
        vision=DisabledVisionCapability(),
    )


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
        runtime=_runtime(),
        settings=get_settings(),
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
            return {"PROJ": VISIBLE, "OTHER": FOREIGN}.get(key)

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

    class Calendar:
        async def get_range(self, *, project_id: int, date_from: date, date_to: date, today: date):
            return SimpleNamespace(
                range=CalendarRangeSchema(
                    date_from=date_from,
                    date_to=date_to,
                    today=today,
                ),
                tasks=[
                    CalendarTaskSchema(
                        id=10,
                        key="PROJ-1",
                        title="Настроить вход",
                        start_date=date(2026, 9, 1),
                        due_date=date(2026, 9, 5),
                        baseline_start_date=date(2026, 9, 1),
                        baseline_due_date=date(2026, 9, 4),
                        drift_days=1,
                        stage_id=1,
                        wbs_node_id=None,
                        priority=TaskPriority.HIGH,
                        assignee="Борис",
                        is_done=False,
                        is_overdue=True,
                        is_due_soon=False,
                        risk_level="high",
                        risk_reasons=[
                            CalendarRiskReasonSchema(
                                code="OVERDUE",
                                message="Срок просрочен.",
                                days=1,
                            )
                        ],
                        updated_at=datetime.now(UTC),
                    )
                ],
                milestones=[
                    CalendarMilestoneSchema(
                        id=3,
                        title="MVP",
                        due_date=date(2026, 9, 20),
                        status=ProjectMilestoneStatus.PLANNED,
                        wbs_node_id=None,
                        description_md=None,
                    )
                ],
                summary=CalendarSummarySchema(
                    overdue=1,
                    due_soon=0,
                    unscheduled=1,
                    drifted=1,
                    dependency_risks=0,
                ),
            )

        async def get_unscheduled(self, **kwargs):
            item = (
                (
                    await self.get_range(
                        project_id=kwargs["project_id"],
                        date_from=date(2026, 9, 1),
                        date_to=date(2026, 9, 30),
                        today=kwargs["today"],
                    )
                )
                .tasks[0]
                .model_copy(update={"start_date": None, "due_date": None})
            )
            return UnscheduledTasksPageSchema(items=[item], next_cursor=None)

    class Milestones:
        def __init__(self, session):
            pass

        async def get_by_project(self, project_id: int):
            return [
                SimpleNamespace(
                    id=3,
                    title="MVP",
                    due_date=date(2026, 9, 20),
                    status=ProjectMilestoneStatus.PLANNED,
                    description_md="Первая версия",
                )
            ]

    monkeypatch.setattr(srv, "tool_context", fake_tool_context)
    for module in (srv, __import__("src.mcp_server.context", fromlist=["x"])):
        monkeypatch.setattr(module, "ProjectsRepository", Projects, raising=False)
        monkeypatch.setattr(module, "ProjectMembersRepository", Members, raising=False)
        monkeypatch.setattr(module, "TasksRepository", Tasks, raising=False)
    monkeypatch.setattr(srv, "ProjectStagesRepository", Stages)
    monkeypatch.setattr(srv, "TaskCommentsRepository", Comments)
    monkeypatch.setattr(srv, "build_calendar_service", lambda session: Calendar())
    monkeypatch.setattr(srv, "MilestonesRepository", Milestones)


async def test_list_projects_hides_foreign_projects(tracker) -> None:
    """Проект, в котором пользователь не состоит, в списке не появляется."""
    result = await srv.list_projects(FakeContext())

    assert [item["project_key"] for item in result] == ["PROJ"]


async def test_get_project_returns_stages_with_counts(tracker) -> None:
    """Карточка проекта содержит стадии и число задач в каждой."""
    result = await srv.get_project(FakeContext(), project_key="PROJ")

    assert result["project_key"] == "PROJ"
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
    """Наружу отдаются ключи вида PROJ-1, а не числовые идентификаторы."""
    result = await srv.list_tasks(FakeContext(), project_key="PROJ")

    assert [item["task_key"] for item in result] == ["PROJ-1", "PROJ-2"]
    assert all("id" not in item for item in result)


async def test_list_tasks_filters_by_stage(tracker) -> None:
    """Фильтр по названию стадии работает без учёта регистра."""
    result = await srv.list_tasks(FakeContext(), project_key="PROJ", stage="в работе")

    assert [item["task_key"] for item in result] == ["PROJ-1"]


async def test_list_tasks_unknown_stage_lists_available(tracker) -> None:
    """Неизвестная стадия подсказывает доступные, а не молча отдаёт пустоту."""
    with pytest.raises(ToolError) as error:
        await srv.list_tasks(FakeContext(), project_key="PROJ", stage="Неизвестная")

    assert "В работе" in str(error.value)


async def test_list_tasks_filters_by_assignee(tracker) -> None:
    """Фильтр по исполнителю сравнивает без учёта регистра."""
    result = await srv.list_tasks(FakeContext(), project_key="PROJ", assignee="анна")

    assert [item["task_key"] for item in result] == ["PROJ-2"]


async def test_list_tasks_only_open_drops_done_stage(tracker) -> None:
    """Флаг только незавершённых отбрасывает задачи завершающей стадии."""
    result = await srv.list_tasks(FakeContext(), project_key="PROJ", only_open=True)

    assert [item["task_key"] for item in result] == ["PROJ-1"]


async def test_list_tasks_respects_limit(tracker) -> None:
    """Лимит ограничивает выдачу: агент не вытянет проект целиком случайно."""
    result = await srv.list_tasks(FakeContext(), project_key="PROJ", limit=1)

    assert len(result) == 1


async def test_get_task_returns_details_and_comment_count(tracker) -> None:
    """Карточка задачи содержит описание и число комментариев."""
    result = await srv.get_task(FakeContext(), task_key="PROJ-1")

    assert result["task_key"] == "PROJ-1"
    assert result["description"] == "Описание"
    assert result["comment_count"] == 1
    assert result["is_done"] is False


async def test_get_task_marks_done_stage(tracker) -> None:
    """Завершённость берётся из признака стадии, а не из поля задачи."""
    result = await srv.get_task(FakeContext(), task_key="PROJ-2")

    assert result["is_done"] is True


async def test_list_comments_returns_body_and_author(tracker) -> None:
    """Комментарии отдаются с автором и ключом задачи."""
    result = await srv.list_comments(FakeContext(), task_key="PROJ-1")

    assert result[0]["task_key"] == "PROJ-1"
    assert result[0]["author"] == "Борис"
    assert result[0]["body"] == "Ждём уточнения"


async def test_search_tasks_finds_by_text(tracker) -> None:
    """Лексический поиск возвращает совпавшие задачи."""
    result = await srv.search_tasks(FakeContext(), project_key="PROJ", query="вход")

    assert [item["task_key"] for item in result] == ["PROJ-1"]


async def test_search_tasks_returns_empty_without_matches(tracker) -> None:
    """Отсутствие совпадений — пустой список, а не ошибка."""
    result = await srv.search_tasks(FakeContext(), project_key="PROJ", query="ничего")

    assert result == []


async def test_search_tasks_rejects_foreign_project(tracker) -> None:
    """Поиск не выполняется в недоступном проекте."""
    with pytest.raises(ToolError):
        await srv.search_tasks(FakeContext(), project_key="OTHER", query="вход")


async def test_get_calendar_range_returns_display_keys_and_backend_risks(tracker) -> None:
    """Календарный tool не раскрывает id и отдаёт готовые причины риска."""
    result = await srv.get_calendar_range(
        FakeContext(),
        project_key="PROJ",
        date_from="2026-09-01",
        date_to="2026-09-30",
    )

    assert result["tasks"][0]["task_key"] == "PROJ-1"
    assert result["tasks"][0]["risk_reasons"][0]["code"] == "OVERDUE"
    assert "id" not in result["tasks"][0]
    assert result["milestones"][0]["title"] == "MVP"


async def test_list_tasks_without_due_date_is_bounded_and_uses_keys(tracker) -> None:
    """Backlog без срока возвращается ограниченным списком с task_key."""
    result = await srv.list_tasks_without_due_date(
        FakeContext(),
        project_key="PROJ",
        limit=1,
    )

    assert result[0]["task_key"] == "PROJ-1"
    assert result[0]["risk_reasons"] == [
        {"code": "OVERDUE", "message": "Срок просрочен.", "days": 1}
    ]


async def test_list_milestones_includes_system_project_deadline(tracker) -> None:
    """Системная веха дедлайна добавляется без отдельной записи в БД."""
    result = await srv.list_milestones(FakeContext(), project_key="PROJ")

    assert [(item["title"], item["is_system"]) for item in result] == [
        ("MVP", False),
        ("Дедлайн проекта", True),
    ]
