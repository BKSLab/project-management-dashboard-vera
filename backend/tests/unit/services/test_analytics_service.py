import json
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.clients.llm import LlmClient
from src.db.models.analytics_reports import AnalyticsReport
from src.db.models.project_milestones import ProjectMilestoneStatus
from src.db.models.projects import ProjectStatus
from src.db.models.tasks import TaskPriority
from src.exceptions.analytics import AnalyticsEmptyScopeError, AnalyticsServiceError
from src.exceptions.projects import ProjectNotFoundError, ProjectsRepositoryError
from src.prompts.analytics import (
    ANALYTICS_PORTFOLIO_SYSTEM_PROMPT,
    ANALYTICS_PROJECT_SYSTEM_PROMPT,
)
from src.schemas.analytics import (
    AnalyticsDraftSchema,
    AnalyticsFindingDraftSchema,
    AnalyticsFindingKind,
    AnalyticsHealth,
    AnalyticsHorizon,
    AnalyticsRecommendationDraftSchema,
    AnalyticsScope,
    AnalyticsSeverity,
)
from src.services.analytics import PORTFOLIO_ATTENTION_TASKS, AnalyticsService
from src.services.db_scope import AnalyticsDbScope

TODAY = date.today()
USER_ID = 7
PROJECT_ID = 1


ACTOR_NAME = "Тестов Тест"


def actor() -> dict:
    """Возвращает автора анализа значениями, а не ORM-моделью."""
    return {"actor_id": USER_ID, "actor_name": ACTOR_NAME}


def project() -> SimpleNamespace:
    """Возвращает дублёр проекта области анализа."""
    return SimpleNamespace(
        id=PROJECT_ID,
        key="PROJ",
        name="Проект",
        description_md="Описание проекта.",
        status=ProjectStatus.ACTIVE,
        color="#58a6ff",
        icon=None,
        start_date=None,
        due_date=None,
    )


def stage(stage_id: int, name: str, is_done: bool) -> SimpleNamespace:
    """Возвращает дублёр стадии канбана."""
    return SimpleNamespace(
        id=stage_id,
        project_id=PROJECT_ID,
        name=name,
        order_index=stage_id,
        color="#58a6ff",
        is_done_stage=is_done,
    )


def task(
    task_id: int,
    stage_id: int,
    due_date: date | None = None,
    assignee: str | None = "Исполнитель",
    updated_days_ago: int = 0,
    wbs_node_id: int | None = None,
) -> SimpleNamespace:
    """Возвращает дублёр задачи проекта."""
    return SimpleNamespace(
        id=task_id,
        project_id=PROJECT_ID,
        number=task_id,
        title=f"Задача {task_id}",
        description_md=None,
        stage_id=stage_id,
        wbs_node_id=wbs_node_id,
        priority=TaskPriority.HIGH,
        role=None,
        assignee=assignee,
        start_date=None,
        due_date=due_date,
        updated_at=datetime.now(UTC) - timedelta(days=updated_days_ago),
    )


def draft(task_keys: list[str]) -> AnalyticsDraftSchema:
    """Возвращает ответ модели со ссылками на указанные задачи."""
    return AnalyticsDraftSchema(
        headline="Работы идут, но сроки по интеграции сорваны.",
        health=AnalyticsHealth.RISK,
        health_note="Просрочки собрались в одном блоке.",
        findings=[
            AnalyticsFindingDraftSchema(
                kind=AnalyticsFindingKind.OVERDUE,
                severity=AnalyticsSeverity.HIGH,
                title="Интеграция просрочена",
                detail="Срок прошёл, в комментариях ждут доступы.",
                project_key="PROJ",
                task_keys=task_keys,
            )
        ],
        progress=[],
        recommendations=[
            AnalyticsRecommendationDraftSchema(
                horizon=AnalyticsHorizon.TODAY,
                title="Назначить владельца блока",
                detail="Иначе срок не за кем закрепить.",
                project_key="ДРУГОЙ",
                task_keys=[],
            )
        ],
    )


def build_service(
    *,
    projects: list | None = None,
    allowed_ids: set[int] | None = None,
    stages: list | None = None,
    tasks: list | None = None,
    dependencies: list | None = None,
    milestones: list | None = None,
    llm_response: AnalyticsDraftSchema | None = None,
    saved_report: AnalyticsReport | None = None,
) -> tuple[AnalyticsService, AsyncMock]:
    """Собирает сервис аналитики с подменёнными репозиториями и моделью."""
    projects = [project()] if projects is None else projects
    allowed_ids = {item.id for item in projects} if allowed_ids is None else allowed_ids

    projects_repository = AsyncMock()
    projects_repository.get_all.return_value = projects
    projects_repository.get_by_id.return_value = projects[0] if projects else None

    members_repository = AsyncMock()
    members_repository.get_project_ids_for_user.return_value = allowed_ids

    stages_repository = AsyncMock()
    stages_repository.get_by_project.return_value = stages or []

    tasks_repository = AsyncMock()
    tasks_repository.get_by_project.return_value = tasks or []

    comments_repository = AsyncMock()
    comments_repository.get_for_tasks.return_value = []

    activity_repository = AsyncMock()
    activity_repository.get_recent_by_project.return_value = []

    dependencies_repository = AsyncMock()
    dependencies_repository.get_by_project.return_value = dependencies or []

    wbs_nodes_repository = AsyncMock()
    wbs_nodes_repository.get_by_project.return_value = []

    milestones_repository = AsyncMock()
    milestones_repository.get_by_project.return_value = milestones or []

    stickers_repository = AsyncMock()
    stickers_repository.list_by_project_id.return_value = []

    documents_repository = AsyncMock()
    documents_repository.get_by_project.return_value = []

    document_links_repository = AsyncMock()
    document_links_repository.get_for_documents.return_value = []

    report = saved_report or AnalyticsReport(
        id=1,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        created_by_display_name_snapshot="Тестов Тест",
        llm_model="test-model",
        duration_ms=10,
        payload={},
        context_summary={},
        created_at=datetime.now(UTC),
    )
    reports_repository = AsyncMock()
    reports_repository.save.side_effect = lambda data: _stored(report, data)

    llm_client = AsyncMock(spec=LlmClient)
    llm_client.get_structured_response.return_value = llm_response or draft([])
    # Имя модели сервис берёт у клиента, а не у глобальных настроек.
    llm_client.model = "test-model"

    db = AnalyticsDbScope(
        reports=reports_repository,
        projects=projects_repository,
        members=members_repository,
        stages=stages_repository,
        tasks=tasks_repository,
        comments=comments_repository,
        activity=activity_repository,
        dependencies=dependencies_repository,
        wbs_nodes=wbs_nodes_repository,
        milestones=milestones_repository,
        stickers=stickers_repository,
        documents=documents_repository,
        document_links=document_links_repository,
        unit_of_work=AsyncMock(),
    )

    @asynccontextmanager
    async def scope():
        yield db

    service = AnalyticsService(scope=scope, llm_client=llm_client)
    return service, reports_repository, db


@pytest.mark.asyncio
async def test_generate_counts_signals_from_database_not_from_model() -> None:
    stages = [stage(1, "В работе", False), stage(2, "Готово", True)]
    tasks = [
        task(11, stage_id=1, due_date=TODAY - timedelta(days=3)),
        task(12, stage_id=1, due_date=TODAY + timedelta(days=2)),
        task(13, stage_id=1, due_date=None, assignee=None, updated_days_ago=30),
        task(14, stage_id=2, due_date=TODAY - timedelta(days=9)),
    ]
    dependencies = [SimpleNamespace(predecessor_task_id=11, successor_task_id=12)]
    milestones = [
        SimpleNamespace(
            title="Веха",
            due_date=TODAY - timedelta(days=1),
            status=ProjectMilestoneStatus.PLANNED,
        )
    ]
    service, reports_repository, _db = build_service(
        stages=stages,
        tasks=tasks,
        dependencies=dependencies,
        milestones=milestones,
    )

    await service.generate(**actor(), project_id=PROJECT_ID)

    signals = reports_repository.save.call_args.kwargs["data"]["payload"]["signals"]
    assert signals["total_tasks"] == 4
    assert signals["done_tasks"] == 1
    assert signals["overdue_tasks"] == 1
    assert signals["due_soon_tasks"] == 1
    assert signals["no_due_date_tasks"] == 1
    assert signals["unassigned_tasks"] == 1
    assert signals["stale_tasks"] == 1
    assert signals["blocked_tasks"] == 1
    assert signals["unplaced_tasks"] == 3
    assert signals["milestones_at_risk"] == 1


@pytest.mark.asyncio
async def test_generate_puts_overdue_tasks_first_in_model_context() -> None:
    stages = [stage(1, "В работе", False)]
    tasks = [
        task(11, stage_id=1, due_date=None),
        task(12, stage_id=1, due_date=TODAY - timedelta(days=4)),
        task(13, stage_id=1, due_date=TODAY + timedelta(days=1)),
    ]
    service, _, db = build_service(stages=stages, tasks=tasks)

    await service.generate(**actor(), project_id=PROJECT_ID)

    llm_client = service.llm_client
    content = json.loads(llm_client.get_structured_response.call_args.kwargs["content"])
    assert [item["key"] for item in content["projects"][0]["tasks"]] == [
        "PROJ-12",
        "PROJ-13",
        "PROJ-11",
    ]


@pytest.mark.asyncio
async def test_generate_reports_context_boundaries_to_user() -> None:
    """Портфельная сводка честно называет, сколько задач в неё вошло.

    Портфель берёт от каждого проекта только проблемные и недавно закрытые
    задачи: пользователь должен видеть, что разбор шёл не по всем 240.
    """
    stages = [stage(1, "В работе", False)]
    tasks = [task(index, stage_id=1) for index in range(1, 121)]
    service, reports_repository, _db = build_service(
        projects=[project(), SimpleNamespace(**vars(project()) | {"id": 2, "key": "SECOND"})],
        stages=stages,
        tasks=tasks,
    )

    await service.generate(**actor(), project_id=None)

    context = reports_repository.save.call_args.kwargs["data"]["context_summary"]
    assert context["tasks_total"] == 240
    assert context["tasks_included"] == PORTFOLIO_ATTENTION_TASKS * 2
    assert context["truncated"] is True
    assert context["omitted"]


@pytest.mark.asyncio
async def test_generate_distinguishes_empty_scope_absence_and_failure() -> None:
    """Пустой срез, чужой проект и сбой базы отвечают тремя разными ошибками."""
    service, _, _db = build_service(stages=[stage(1, "В работе", False)], tasks=[])
    with pytest.raises(AnalyticsEmptyScopeError):
        await service.generate(**actor(), project_id=PROJECT_ID)

    service, _, _db = build_service(allowed_ids=set())
    with pytest.raises(ProjectNotFoundError):
        await service.generate(**actor(), project_id=PROJECT_ID)

    service, _, db = build_service()
    db.projects.get_by_id.side_effect = ProjectsRepositoryError("сбой")
    with pytest.raises(AnalyticsServiceError):
        await service.generate(**actor(), project_id=PROJECT_ID)


@pytest.mark.asyncio
async def test_get_latest_checks_access_and_picks_the_right_report() -> None:
    """Отсутствие отчёта — не ошибка, чужой проект — 404, портфель — по автору."""
    service, reports_repository, _db = build_service()
    reports_repository.get_latest_for_project.return_value = None
    assert await service.get_latest(user_id=USER_ID, project_id=PROJECT_ID) is None

    service, _, _db = build_service(allowed_ids=set())
    with pytest.raises(ProjectNotFoundError):
        await service.get_latest(user_id=USER_ID, project_id=PROJECT_ID)

    service, reports_repository, _db = build_service()
    reports_repository.get_latest_portfolio.return_value = None
    await service.get_latest(user_id=USER_ID, project_id=None)
    reports_repository.get_latest_portfolio.assert_awaited_once_with(user_id=USER_ID)


def _stored(report: AnalyticsReport, data: dict) -> AnalyticsReport:
    """Возвращает запись так, как её вернул бы репозиторий после сохранения."""
    report.payload = data["payload"]
    report.context_summary = data["context_summary"]
    report.llm_model = data["llm_model"]
    report.duration_ms = data["duration_ms"]
    return report


@pytest.mark.asyncio
async def test_report_payload_keeps_only_verifiable_references() -> None:
    """Ссылки на задачи разрешаются, несуществующие отбрасываются, отчёт возвращается схемой."""

    stages = [stage(1, "В работе", False), stage(2, "Готово", True)]
    tasks = [task(11, stage_id=1, due_date=TODAY - timedelta(days=5))]
    service, reports_repository, _db = build_service(
        stages=stages,
        tasks=tasks,
        llm_response=draft(["PROJ-11"]),
    )

    await service.generate(**actor(), project_id=PROJECT_ID)

    payload = reports_repository.save.call_args.kwargs["data"]["payload"]
    assert payload["findings"][0]["tasks"] == [
        {
            "id": 11,
            "key": "PROJ-11",
            "title": "Задача 11",
            "project_key": "PROJ",
            "due_date": (TODAY - timedelta(days=5)).isoformat(),
            "is_overdue": True,
        }
    ]
    # Ссылки модели на несуществующие задачу и проект отбрасываются. Модель свободна назвать любой ключ, а отчёт обязан ссылаться только на то, что действительно попало в срез: иначе в интерфейсе появится ссылка в никуда.
    stages = [stage(1, "В работе", False)]
    tasks = [task(11, stage_id=1)]
    service, reports_repository, _db = build_service(
        stages=stages,
        tasks=tasks,
        llm_response=draft(["PROJ-999", "OTHER-1"]),
    )

    await service.generate(**actor(), project_id=PROJECT_ID)

    payload = reports_repository.save.call_args.kwargs["data"]["payload"]
    assert payload["findings"][0]["tasks"] == []

    service, reports_repository, _db = build_service(stages=stages, tasks=[task(11, stage_id=1)])

    await service.generate(**actor(), project_id=PROJECT_ID)

    payload = reports_repository.save.call_args.kwargs["data"]["payload"]
    assert payload["recommendations"][0]["project_key"] is None

    stages = [stage(1, "В работе", False)]
    saved = AnalyticsReport(
        id=42,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        created_by_display_name_snapshot="Тестов Тест",
        llm_model="test-model",
        duration_ms=10,
        payload={},
        context_summary={},
        created_at=datetime.now(UTC),
    )
    service, _, db = build_service(
        stages=stages,
        tasks=[task(11, stage_id=1)],
        saved_report=saved,
    )

    result = await service.generate(**actor(), project_id=PROJECT_ID)

    assert result.id == 42
    assert result.scope is AnalyticsScope.PROJECT
    assert result.project_key == "PROJ"
    assert result.health is AnalyticsHealth.RISK
    assert result.findings[0].kind is AnalyticsFindingKind.OVERDUE


@pytest.mark.asyncio
async def test_portfolio_takes_only_projects_in_work() -> None:
    """Сводка дашборда разбирает активные проекты и молчит про остальные.

    Приостановленный, завершённый и ещё не начатый проект решения на
    сегодня не требуют, а место в контексте занимают наравне с активными.
    Если активных нет вовсе, это не пустой отчёт, а явный отказ.
    """
    active = project()
    paused = SimpleNamespace(**vars(project()) | {"id": 2, "key": "PAUSE", "status": ProjectStatus.PAUSED})
    service, reports_repository, _db = build_service(
        projects=[active, paused],
        stages=[stage(1, "В работе", False)],
        tasks=[task(11, stage_id=1)],
    )

    await service.generate(**actor(), project_id=None)

    content = json.loads(service.llm_client.get_structured_response.call_args.kwargs["content"])
    assert [item["key"] for item in content["projects"]] == ["PROJ"]
    assert reports_repository.save.call_args.kwargs["data"]["context_summary"]["projects"] == 1

    service, _, _db = build_service(
        projects=[paused],
        stages=[stage(1, "В работе", False)],
        tasks=[task(11, stage_id=1)],
    )

    with pytest.raises(AnalyticsEmptyScopeError) as error:
        await service.generate(**actor(), project_id=None)

    assert "в работе" in error.value.error_details


@pytest.mark.asyncio
async def test_each_scope_gets_its_own_prompt() -> None:
    """Портфель и проект разбираются разными prompt-ами.

    Вопросы у областей разные: «за какой проект браться» против «что
    происходит внутри проекта». Общий prompt отвечал на оба посредственно.
    """
    service, _, _db = build_service(
        stages=[stage(1, "В работе", False)],
        tasks=[task(11, stage_id=1)],
    )

    await service.generate(**actor(), project_id=None)
    portfolio_prompt = service.llm_client.get_structured_response.call_args.kwargs["system_prompt"]

    await service.generate(**actor(), project_id=PROJECT_ID)
    project_prompt = service.llm_client.get_structured_response.call_args.kwargs["system_prompt"]

    assert portfolio_prompt == ANALYTICS_PORTFOLIO_SYSTEM_PROMPT
    assert project_prompt == ANALYTICS_PROJECT_SYSTEM_PROMPT
    assert portfolio_prompt != project_prompt


@pytest.mark.asyncio
async def test_portfolio_slice_carries_project_signals_instead_of_task_details() -> None:
    """Портфельный срез — сводка по проектам, а не разбор их внутренностей.

    По каждому проекту модель получает показатели, ближайшие вехи и
    несколько задач как доказательство. Комментарии, документы, стикеры,
    ИСР и история сюда не попадают: на уровне портфеля они не помогают
    выбрать проект, а бюджет контекста тратят быстрее всего.
    """
    stages = [stage(1, "В работе", False), stage(2, "Готово", True)]
    tasks = [
        task(11, stage_id=1, due_date=TODAY - timedelta(days=3)),
        task(12, stage_id=1, due_date=TODAY + timedelta(days=2)),
        task(13, stage_id=2),
    ]
    milestones = [
        SimpleNamespace(
            title="Веха",
            due_date=TODAY - timedelta(days=1),
            status=ProjectMilestoneStatus.PLANNED,
        )
    ]
    service, _, db = build_service(stages=stages, tasks=tasks, milestones=milestones)

    await service.generate(**actor(), project_id=None)

    content = json.loads(service.llm_client.get_structured_response.call_args.kwargs["content"])
    entry = content["projects"][0]
    assert set(entry) == {
        "key",
        "name",
        "status",
        "description",
        "start_date",
        "due_date",
        "signals",
        "milestones",
        "attention_tasks",
        "recently_closed",
    }
    assert entry["signals"]["overdue_tasks"] == 1
    assert entry["signals"]["done_tasks"] == 1
    assert [item["title"] for item in entry["milestones"]] == ["Веха"]
    # Завершённая задача попадает в подтверждение движения, а не в проблемы.
    assert [item["key"] for item in entry["attention_tasks"]] == ["PROJ-11", "PROJ-12"]
    assert [item["key"] for item in entry["recently_closed"]] == ["PROJ-13"]
    assert entry["attention_tasks"][0]["days_overdue"] == 3

    # Тяжёлые источники для портфеля даже не читаются.
    db.comments.get_for_tasks.assert_not_awaited()
    db.documents.get_by_project.assert_not_awaited()
    db.stickers.list_by_project_id.assert_not_awaited()
    db.activity.get_recent_by_project.assert_not_awaited()
    db.wbs_nodes.get_by_project.assert_not_awaited()
