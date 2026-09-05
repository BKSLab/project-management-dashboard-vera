import json
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
from src.services.analytics import AnalyticsService

TODAY = date.today()
USER_ID = 7
PROJECT_ID = 1


def user() -> SimpleNamespace:
    """Возвращает дублёр пользователя, запросившего анализ."""
    return SimpleNamespace(
        id=USER_ID,
        username="tester",
        last_name="Тестов",
        first_name="Тест",
        middle_name=None,
    )


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

    service = AnalyticsService(
        reports_repository=reports_repository,
        projects_repository=projects_repository,
        members_repository=members_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        comments_repository=comments_repository,
        activity_repository=activity_repository,
        dependencies_repository=dependencies_repository,
        wbs_nodes_repository=wbs_nodes_repository,
        milestones_repository=milestones_repository,
        stickers_repository=stickers_repository,
        documents_repository=documents_repository,
        document_links_repository=document_links_repository,
        unit_of_work=AsyncMock(),
        llm_client=llm_client,
    )
    return service, reports_repository


@pytest.mark.asyncio
async def test_generate_saves_report_with_resolved_task_links() -> None:
    stages = [stage(1, "В работе", False), stage(2, "Готово", True)]
    tasks = [task(11, stage_id=1, due_date=TODAY - timedelta(days=5))]
    service, reports_repository = build_service(
        stages=stages,
        tasks=tasks,
        llm_response=draft(["PROJ-11"]),
    )

    await service.generate(user=user(), project_id=PROJECT_ID)

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


@pytest.mark.asyncio
async def test_generate_drops_task_keys_absent_in_scope() -> None:
    stages = [stage(1, "В работе", False)]
    tasks = [task(11, stage_id=1)]
    service, reports_repository = build_service(
        stages=stages,
        tasks=tasks,
        llm_response=draft(["PROJ-999", "OTHER-1"]),
    )

    await service.generate(user=user(), project_id=PROJECT_ID)

    payload = reports_repository.save.call_args.kwargs["data"]["payload"]
    assert payload["findings"][0]["tasks"] == []


@pytest.mark.asyncio
async def test_generate_drops_unknown_project_key() -> None:
    stages = [stage(1, "В работе", False)]
    service, reports_repository = build_service(stages=stages, tasks=[task(11, stage_id=1)])

    await service.generate(user=user(), project_id=PROJECT_ID)

    payload = reports_repository.save.call_args.kwargs["data"]["payload"]
    assert payload["recommendations"][0]["project_key"] is None


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
    service, reports_repository = build_service(
        stages=stages,
        tasks=tasks,
        dependencies=dependencies,
        milestones=milestones,
    )

    await service.generate(user=user(), project_id=PROJECT_ID)

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
    service, _ = build_service(stages=stages, tasks=tasks)

    await service.generate(user=user(), project_id=PROJECT_ID)

    llm_client = service.llm_client
    content = json.loads(llm_client.get_structured_response.call_args.kwargs["content"])
    assert [item["key"] for item in content["projects"][0]["tasks"]] == [
        "PROJ-12",
        "PROJ-13",
        "PROJ-11",
    ]


@pytest.mark.asyncio
async def test_generate_reports_context_boundaries_to_user() -> None:
    stages = [stage(1, "В работе", False)]
    tasks = [task(index, stage_id=1) for index in range(1, 121)]
    service, reports_repository = build_service(
        projects=[project(), SimpleNamespace(**vars(project()) | {"id": 2, "key": "SECOND"})],
        stages=stages,
        tasks=tasks,
    )

    await service.generate(user=user(), project_id=None)

    context = reports_repository.save.call_args.kwargs["data"]["context_summary"]
    assert context["tasks_total"] == 240
    assert context["tasks_included"] == 120
    assert context["truncated"] is True
    assert context["omitted"]


@pytest.mark.asyncio
async def test_generate_raises_empty_scope_when_projects_have_no_tasks() -> None:
    service, _ = build_service(stages=[stage(1, "В работе", False)], tasks=[])

    with pytest.raises(AnalyticsEmptyScopeError):
        await service.generate(user=user(), project_id=PROJECT_ID)


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_foreign_project() -> None:
    service, _ = build_service(allowed_ids=set())

    with pytest.raises(ProjectNotFoundError):
        await service.generate(user=user(), project_id=PROJECT_ID)


@pytest.mark.asyncio
async def test_generate_raises_service_error_when_repository_fails() -> None:
    service, _ = build_service()
    service.projects_repository.get_by_id.side_effect = ProjectsRepositoryError("сбой")

    with pytest.raises(AnalyticsServiceError):
        await service.generate(user=user(), project_id=PROJECT_ID)


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_report_missing() -> None:
    service, reports_repository = build_service()
    reports_repository.get_latest_for_project.return_value = None

    assert await service.get_latest(user_id=USER_ID, project_id=PROJECT_ID) is None


@pytest.mark.asyncio
async def test_get_latest_raises_not_found_for_foreign_project() -> None:
    service, _ = build_service(allowed_ids=set())

    with pytest.raises(ProjectNotFoundError):
        await service.get_latest(user_id=USER_ID, project_id=PROJECT_ID)


@pytest.mark.asyncio
async def test_get_latest_portfolio_report_is_selected_by_author() -> None:
    service, reports_repository = build_service()
    reports_repository.get_latest_portfolio.return_value = None

    await service.get_latest(user_id=USER_ID, project_id=None)

    reports_repository.get_latest_portfolio.assert_awaited_once_with(user_id=USER_ID)


@pytest.mark.asyncio
async def test_generate_returns_saved_report_as_schema() -> None:
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
    service, _ = build_service(
        stages=stages,
        tasks=[task(11, stage_id=1)],
        saved_report=saved,
    )

    result = await service.generate(user=user(), project_id=PROJECT_ID)

    assert result.id == 42
    assert result.scope is AnalyticsScope.PROJECT
    assert result.project_key == "PROJ"
    assert result.health is AnalyticsHealth.RISK
    assert result.findings[0].kind is AnalyticsFindingKind.OVERDUE


def _stored(report: AnalyticsReport, data: dict) -> AnalyticsReport:
    """Возвращает запись так, как её вернул бы репозиторий после сохранения."""
    report.payload = data["payload"]
    report.context_summary = data["context_summary"]
    report.llm_model = data["llm_model"]
    report.duration_ms = data["duration_ms"]
    return report
