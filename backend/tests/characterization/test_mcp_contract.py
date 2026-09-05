"""Публичный контракт MCP: имена инструментов, входные схемы и форма ответа.

Этап 8 переводит MCP-инструменты с прямых репозиториев на сервисный слой.
Наружу при этом не должно измениться ничего: ни набор инструментов, ни их
входные схемы, ни ключи JSON, который видит вызывающая модель.
"""

from datetime import UTC, date, datetime

from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project, ProjectStatus
from src.db.models.task_comments import TaskComment
from src.db.models.tasks import Task, TaskPriority
from src.mcp_server.presenters import (
    TEXT_LIMIT,
    TRUNCATION_NOTE,
    comment_item,
    project_detail,
    project_summary,
    shorten,
    task_detail,
    task_summary,
)
from src.mcp_server.server import mcp_server

EXPECTED_TOOLS = {
    "list_projects",
    "get_project",
    "list_tasks",
    "get_task",
    "list_comments",
    "search_tasks",
    "search_project_knowledge",
    "get_calendar_range",
    "list_tasks_without_due_date",
    "list_milestones",
    "create_task",
    "update_task",
    "move_task",
    "delete_task",
    "add_comment",
    "set_task_dates",
    "create_milestone",
}

# Обязательные поля каждого инструмента: изменение этого множества ломает
# уже настроенных внешних клиентов.
EXPECTED_REQUIRED = {
    "list_projects": set(),
    "get_project": {"project_key"},
    "list_tasks": {"project_key"},
    "get_task": {"task_key"},
    "list_comments": {"task_key"},
    "search_tasks": {"project_key", "query"},
    "search_project_knowledge": {"project_key", "query"},
    "get_calendar_range": {"project_key", "date_from", "date_to"},
    "list_tasks_without_due_date": {"project_key"},
    "list_milestones": {"project_key"},
    "create_task": {"project_key", "title"},
    "update_task": {"task_key"},
    "move_task": {"task_key", "stage"},
    "delete_task": {"task_key"},
    "add_comment": {"task_key", "body"},
    "set_task_dates": {"task_key"},
    "create_milestone": {"project_key", "title", "due_date"},
}


async def test_tool_names_are_frozen() -> None:
    """Набор публичных инструментов не меняется рефакторингом."""
    tools = await mcp_server.list_tools()

    assert {tool.name for tool in tools} == EXPECTED_TOOLS


async def test_required_arguments_are_frozen() -> None:
    """Обязательные аргументы каждого инструмента остаются прежними."""
    tools = {tool.name: tool for tool in await mcp_server.list_tools()}

    actual = {
        name: set(tools[name].input_schema.get("required", [])) for name in EXPECTED_REQUIRED
    }

    assert actual == EXPECTED_REQUIRED


async def test_tools_never_expose_numeric_ids() -> None:
    """Наружу отдаются отображаемые ключи, а не первичные ключи БД."""
    tools = await mcp_server.list_tools()

    for tool in tools:
        properties = set(tool.input_schema.get("properties", {}))
        forbidden = properties & {"project_id", "task_id", "comment_id", "milestone_id"}
        assert not forbidden, f"{tool.name} принимает числовой идентификатор: {forbidden}."


async def test_every_tool_keeps_its_description() -> None:
    """Описание — часть контракта: по нему модель выбирает инструмент."""
    tools = await mcp_server.list_tools()

    for tool in tools:
        assert tool.description, f"У инструмента {tool.name} нет описания."


def _project() -> Project:
    """Проект с заполненными полями представления."""
    return Project(
        id=1,
        owner_id=1,
        key="CHAR",
        name="Характеризация",
        color="#58a6ff",
        status=ProjectStatus.ACTIVE,
        description_md="Описание проекта.",
        start_date=date(2026, 9, 1),
        due_date=date(2026, 12, 31),
    )


def _stage() -> ProjectStage:
    """Стадия проекта."""
    return ProjectStage(id=10, project_id=1, name="В работе", is_done_stage=False)


def _task() -> Task:
    """Задача проекта."""
    return Task(
        id=100,
        project_id=1,
        stage_id=10,
        number=142,
        title="Собрать отчёт",
        description_md="Подробности задачи.",
        priority=TaskPriority.HIGH,
        assignee="Борис",
        due_date=date(2026, 10, 1),
    )


def test_project_summary_keys_are_frozen() -> None:
    """Карточка проекта в списке сохраняет свои ключи."""
    result = project_summary(_project())

    assert set(result) == {"project_key", "name", "status", "start_date", "due_date"}
    assert result["project_key"] == "CHAR"
    assert result["start_date"] == "2026-09-01"


def test_project_detail_keys_are_frozen() -> None:
    """Подробная карточка проекта сохраняет свои ключи и форму стадий."""
    result = project_detail(
        _project(),
        stages=[_stage()],
        task_counts={10: 3},
        total_tasks=3,
    )

    assert set(result) == {
        "project_key",
        "name",
        "status",
        "start_date",
        "due_date",
        "description",
        "total_tasks",
        "stages",
    }
    assert result["stages"] == [{"name": "В работе", "is_done_stage": False, "task_count": 3}]


def test_task_summary_keys_are_frozen() -> None:
    """Карточка задачи в списке сохраняет свои ключи и формат ключа задачи."""
    result = task_summary(_task(), project=_project(), stage=_stage())

    assert set(result) == {
        "task_key",
        "title",
        "stage",
        "is_done",
        "priority",
        "assignee",
        "due_date",
    }
    assert result["task_key"] == "CHAR-142"
    assert result["is_done"] is False


def test_task_detail_keys_are_frozen() -> None:
    """Подробная карточка задачи сохраняет свои ключи."""
    result = task_detail(
        _task(),
        project=_project(),
        stage=_stage(),
        wbs_path="1.2 Раздел",
        comment_count=2,
    )

    assert set(result) == {
        "task_key",
        "title",
        "stage",
        "is_done",
        "priority",
        "assignee",
        "due_date",
        "role",
        "wbs_path",
        "description",
        "comment_count",
    }


def test_comment_item_keys_are_frozen() -> None:
    """Комментарий сохраняет свои ключи и ISO-формат времени."""
    comment = TaskComment(
        id=1,
        task_id=100,
        author_name="Борис",
        body_md="Текст комментария.",
        created_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    )

    result = comment_item(comment, task_key="CHAR-142")

    assert set(result) == {"task_key", "author", "created_at", "body"}
    assert result["created_at"] == "2026-09-01T10:00:00+00:00"


def test_long_text_is_truncated_with_visible_note() -> None:
    """Обрезка длинного текста остаётся явной: модель не примет её за конец."""
    result = shorten("а" * (TEXT_LIMIT + 100))

    assert result is not None
    assert result.endswith(TRUNCATION_NOTE)
    assert len(result) == TEXT_LIMIT + len(TRUNCATION_NOTE)


def test_short_text_is_returned_unchanged() -> None:
    """Короткий текст не трогается, пустой отдаётся как ``None``."""
    assert shorten("коротко") == "коротко"
    assert shorten("") is None
    assert shorten(None) is None
