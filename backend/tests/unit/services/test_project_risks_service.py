from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.knowledge_index_jobs import KnowledgeEntityType
from src.exceptions.access import ResourceNotAvailableError
from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.project_risks import (
    ProjectRiskNotFoundError,
    ProjectRiskOwnerMismatchError,
    ProjectRiskRepositoryError,
    ProjectRiskServiceError,
    ProjectRiskTaskMismatchError,
)
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_risks import ProjectRiskRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.enums import RiskRating, RiskReasonCode, RiskStatus
from src.schemas.project_risks import (
    ProjectRiskCreateSchema,
    ProjectRiskFilters,
    ProjectRiskUpdateSchema,
)
from src.services.access import AccessService
from src.services.knowledge_events import KnowledgeEvents
from src.services.project_risks import ProjectRiskService, build_risk_summary

TODAY = date(2026, 9, 6)


def risk(**changes):
    return SimpleNamespace(
        **{
            "id": 12,
            "key": "RISK-12",
            "project_id": 1,
            "title": "Задержка CRM",
            "description": "Поставщик может задержать API.",
            "probability": "HIGH",
            "impact": "HIGH",
            "risk_level": "HIGH",
            "status": "OPEN",
            "response_strategy": "MITIGATE",
            "mitigation_plan": "",
            "response_plan": "",
            "owner_user_id": None,
            "task_id": None,
            "review_date": None,
            "source": "MANUAL",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            **changes,
        }
    )


def create_data(**changes):
    return ProjectRiskCreateSchema(
        **{
            "title": "Задержка CRM",
            "description": "Поставщик может задержать API.",
            "probability": "HIGH",
            "impact": "HIGH",
            "response_strategy": "MITIGATE",
            **changes,
        }
    )


def build_service():
    repository = AsyncMock(spec=ProjectRiskRepository)
    repository.save.side_effect = lambda values: risk(**values)
    repository.get_by_id.return_value = risk()
    repository.update.side_effect = lambda current, values: risk(**{**vars(current), **values})
    members = AsyncMock(spec=ProjectMembersRepository)
    tasks = AsyncMock(spec=TasksRepository)
    access = AsyncMock(spec=AccessService)
    events = AsyncMock(spec=KnowledgeEvents)
    uow = AsyncMock(spec=UnitOfWork)
    service = ProjectRiskService(
        risks_repository=repository,
        tasks_repository=tasks,
        members_repository=members,
        access_service=access,
        knowledge_events=events,
        unit_of_work=uow,
        projects_repository=AsyncMock(spec=ProjectsRepository),
    )
    return service, repository, members, tasks, access, events, uow


@pytest.mark.parametrize(
    ("probability", "impact", "expected"),
    [
        ("LOW", "LOW", "LOW"),
        ("LOW", "MEDIUM", "LOW"),
        ("LOW", "HIGH", "MEDIUM"),
        ("MEDIUM", "LOW", "LOW"),
        ("MEDIUM", "MEDIUM", "MEDIUM"),
        ("MEDIUM", "HIGH", "HIGH"),
        ("HIGH", "LOW", "MEDIUM"),
        ("HIGH", "MEDIUM", "HIGH"),
        ("HIGH", "HIGH", "HIGH"),
    ],
)
async def test_create_calculates_all_matrix_combinations_and_commits_outbox(
    probability, impact, expected
):
    service, repository, _, _, access, events, uow = build_service()
    result = await service.create_risk(
        project_id=1,
        user_id=7,
        data=create_data(probability=probability, impact=impact),
    )
    assert result.risk_level == expected
    assert repository.save.await_args.args[0]["risk_level"] == expected
    access.ensure_project_access.assert_awaited_once_with(project_id=1, user_id=7)
    events.upsert.assert_awaited_once_with(
        project_id=1, entity_type=KnowledgeEntityType.RISK, entity_id=12
    )
    uow.commit.assert_awaited_once()


@pytest.mark.parametrize("state", list(RiskStatus))
async def test_status_has_its_own_lifecycle_and_patch_recalculates_using_existing_impact(state):
    service, repository, _, _, _, events, _ = build_service()
    result = await service.update_risk(
        project_id=1,
        risk_id=12,
        user_id=7,
        data=ProjectRiskUpdateSchema(
            probability="LOW", status=state, task_id=None, owner_user_id=None
        ),
    )
    assert result.risk_level == RiskRating.MEDIUM
    assert result.impact == RiskRating.HIGH
    assert result.status == state
    repository.get_by_id.assert_awaited_once_with(project_id=1, risk_id=12, for_update=True)
    events.upsert.assert_awaited_once()


@pytest.mark.parametrize("missing", [False, True])
async def test_task_must_exist_in_same_project(missing):
    service, repository, _, tasks, _, _, uow = build_service()
    tasks.get_by_id.return_value = None if missing else SimpleNamespace(project_id=2)
    with pytest.raises(ProjectRiskTaskMismatchError) as raised:
        await service.create_risk(project_id=1, user_id=7, data=create_data(task_id=99))
    assert raised.value.status_code == 422
    repository.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


async def test_owner_must_be_member_and_membership_is_locked_against_removal():
    service, repository, members, _, _, _, _ = build_service()
    members.get.return_value = None
    with pytest.raises(ProjectRiskOwnerMismatchError) as raised:
        await service.create_risk(project_id=1, user_id=7, data=create_data(owner_user_id=99))
    assert raised.value.status_code == 422
    members.get.assert_awaited_once_with(1, 99, for_update=True)
    repository.save.assert_not_awaited()


@pytest.mark.parametrize("method", ["get_risk", "update_risk", "delete_risk"])
async def test_foreign_or_missing_risk_is_hidden(method):
    service, repository, *_ = build_service()
    repository.get_by_id.return_value = risk(project_id=2)
    kwargs = {"project_id": 1, "risk_id": 12, "user_id": 7}
    if method == "update_risk":
        kwargs["data"] = ProjectRiskUpdateSchema(status="CLOSED")
    with pytest.raises(ProjectRiskNotFoundError) as raised:
        await getattr(service, method)(**kwargs)
    assert raised.value.status_code == 404


async def test_access_denied_stops_before_domain_repository():
    service, repository, _, _, access, _, _ = build_service()
    access.ensure_project_access.side_effect = ResourceNotAvailableError(
        resource="Проект", resource_id=1
    )
    with pytest.raises(ResourceNotAvailableError):
        await service.list_risks(project_id=1, user_id=7, filters=ProjectRiskFilters())
    repository.get_count.assert_not_awaited()


async def test_outbox_failure_rolls_back_create_instead_of_partial_success():
    service, _, _, _, _, events, uow = build_service()
    events.upsert.side_effect = KnowledgeEventsServiceError("Очередь недоступна.")
    with pytest.raises(ProjectRiskServiceError) as raised:
        await service.create_risk(project_id=1, user_id=7, data=create_data())
    assert raised.value.status_code == 500
    uow.commit.assert_not_awaited()
    uow.rollback.assert_awaited_once()


async def test_repository_failure_is_wrapped_and_delete_enqueues_index_removal():
    service, repository, _, _, _, events, uow = build_service()
    repository.get_by_id.side_effect = ProjectRiskRepositoryError("Ошибка чтения.")
    with pytest.raises(ProjectRiskServiceError) as raised:
        await service.get_risk(project_id=1, risk_id=12, user_id=7)
    assert raised.value.status_code == 500
    repository.get_by_id.side_effect = None
    await service.delete_risk(project_id=1, risk_id=12, user_id=7)
    events.delete.assert_awaited_once_with(
        project_id=1, entity_type=KnowledgeEntityType.RISK, entity_id=12
    )
    uow.commit.assert_awaited_once()


def test_summary_separates_occurred_and_closed_and_fills_nine_cells():
    def group(state):
        return {
            "status": state,
            "probability": "HIGH",
            "impact": "HIGH",
            "risk_level": "HIGH",
            "count": 1,
            "without_owner": 1,
            "without_mitigation": 1,
            "due_for_review": 1,
            "review_overdue": 1,
            "linked": 1,
            "ai_suggested": 1,
            "latest_update": datetime.now(UTC),
        }

    result = build_risk_summary([group(state) for state in RiskStatus])
    assert result.total_risks == 4
    assert result.active_risks == result.high_risks == result.risks_without_owner == 3
    assert result.closed_risks == result.occurred_risks == 1
    assert result.risks_linked_to_tasks == result.ai_suggested_risks == 4
    assert len(result.matrix) == 9
    assert sum(cell.count for cell in result.matrix) == 4
    signals = {item.code: item.count for item in result.signals}
    assert signals[RiskReasonCode.HIGH_OPEN_RISK] == 2
    assert signals[RiskReasonCode.RISK_OCCURRED] == 1


async def test_pagination_and_summary_use_entire_filtered_set():
    service, repository, *_ = build_service()
    repository.get_count.return_value = 123
    repository.get_page.return_value = [risk()]
    filters = ProjectRiskFilters(search="CRM", active_only=True, risk_level="HIGH")
    page = await service.list_risks(project_id=1, user_id=7, filters=filters, page=2, page_size=10)
    assert page.total == 123 and page.page == 2 and len(page.items) == 1
    repository.get_aggregates.return_value = []
    summary = await service.get_summary(project_id=1, user_id=7, filters=filters, today=TODAY)
    repository.get_aggregates.assert_awaited_once_with(
        project_ids={1}, filters=filters, today=TODAY
    )
    assert len(summary.matrix) == 9
