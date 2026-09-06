from datetime import date

import pytest
from sqlalchemy import delete, select

from src.db.models.project_risks import ProjectRisk
from src.db.models.projects import Project
from src.db.models.tasks import Task
from src.db.models.users import User
from src.exceptions.project_risks import ProjectRiskRepositoryError
from src.repositories.project_risks import ProjectRiskRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.schemas.project_risks import ProjectRiskFilters
from src.services.project_risks import build_risk_summary


def data(project_id, **changes):
    return {
        "project_id": project_id,
        "title": "Задержка CRM",
        "description": "Описание события.",
        "probability": "HIGH",
        "impact": "HIGH",
        "risk_level": "HIGH",
        "response_strategy": "MITIGATE",
        **changes,
    }


async def test_crud_filters_pagination_aggregates_and_task_counts(db_session, stage, user):
    repository = ProjectRiskRepository(db_session)
    task = await TasksRepository(db_session).save(
        data={
            "project_id": stage.project_id,
            "stage_id": stage.id,
            "number": 142,
            "title": "API",
            "priority": "HIGH",
            "position": 1000,
        }
    )
    first = await repository.save(
        data(stage.project_id, task_id=task.id, owner_user_id=user.id, review_date=date(2026, 9, 5))
    )
    second = await repository.save(
        data(
            stage.project_id,
            title="Недоступность API",
            status="OCCURRED",
            review_date=date(2026, 9, 6),
            source="AI_SUGGESTED",
        )
    )
    await repository.save(data(stage.project_id, title="Закрытый", status="CLOSED"))
    other = await ProjectsRepository(db_session).save(
        data={
            "owner_id": user.id,
            "key": "OTHER",
            "name": "Другой",
            "color": "#000",
            "order_index": 1,
        }
    )
    foreign = await repository.save(data(other.id))
    assert await repository.get_by_id(project_id=stage.project_id, risk_id=foreign.id) is None

    for filters in [
        ProjectRiskFilters(search="crm"),
        ProjectRiskFilters(search=first.key),
        ProjectRiskFilters(owner_user_id=user.id),
        ProjectRiskFilters(task_id=task.id),
        ProjectRiskFilters(probability="HIGH", impact="HIGH", risk_level="HIGH", status="OPEN"),
    ]:
        rows = await repository.get_page(
            project_id=stage.project_id, filters=filters, page=1, page_size=1
        )
        assert [row.id for row in rows] == [first.id]
        assert await repository.get_count(project_id=stage.project_id, filters=filters) == 1
    assert (
        await repository.get_count(
            project_id=stage.project_id, filters=ProjectRiskFilters(search="%")
        )
        == 0
    )
    assert (
        len(
            await repository.get_page(
                project_id=stage.project_id, filters=ProjectRiskFilters(), page=2, page_size=2
            )
        )
        == 1
    )

    groups = await repository.get_aggregates(
        project_ids={stage.project_id}, filters=ProjectRiskFilters(), today=date(2026, 9, 6)
    )
    summary = build_risk_summary(groups)
    assert summary.total_risks == 3 and summary.active_risks == 2
    assert summary.occurred_risks == 1 and summary.closed_risks == 1
    assert summary.risks_due_for_review == 2 and summary.risks_review_overdue == 1
    assert summary.risks_without_owner == 1 and summary.risks_without_mitigation == 2
    assert summary.ai_suggested_risks == 1 and summary.risks_linked_to_tasks == 1
    assert await repository.get_task_counts(stage.project_id) == {task.id: 1}
    assert first.created_at and first.updated_at
    updated = await repository.update(first, {"title": "Уточнённый риск"})
    assert updated.title == "Уточнённый риск" and updated.updated_at
    assert await repository.clear_owner(project_id=stage.project_id, user_id=user.id) == [first.id]
    await repository.delete(second)
    assert await repository.get_by_id(project_id=stage.project_id, risk_id=second.id) is None


async def test_task_and_owner_deletion_preserve_risk_and_project_deletion_cascades(
    db_session, stage, user
):
    repository = ProjectRiskRepository(db_session)
    task = await TasksRepository(db_session).save(
        data={
            "project_id": stage.project_id,
            "stage_id": stage.id,
            "number": 1,
            "title": "API",
            "priority": "HIGH",
            "position": 1000,
        }
    )
    # Другой профиль, чтобы удаление ответственного не удалило проект владельца.
    owner = User(
        username="risk.owner",
        password_hash="hash",
        first_name="Иван",
        last_name="Тестов",
        is_active=True,
    )
    db_session.add(owner)
    await db_session.flush()
    risk = await repository.save(data(stage.project_id, task_id=task.id, owner_user_id=owner.id))
    risk_id = risk.id
    await db_session.execute(delete(Task).where(Task.id == task.id))
    await db_session.execute(delete(User).where(User.id == owner.id))
    row = (
        await db_session.execute(
            select(ProjectRisk)
            .where(ProjectRisk.id == risk_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert row.task_id is None and row.owner_user_id is None
    await db_session.execute(delete(Project).where(Project.id == stage.project_id))
    assert await repository.get_by_id(project_id=stage.project_id, risk_id=risk_id) is None


async def test_fk_and_required_text_constraints_surface_as_repository_errors(db_session, project):
    repository = ProjectRiskRepository(db_session)
    with pytest.raises(ProjectRiskRepositoryError):
        await repository.save(data(project.id, task_id=2_000_000_000))
