import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.projects import Project
from src.db.models.users import User
from src.repositories.analytics_reports import AnalyticsReportsRepository
from src.repositories.users import UsersRepository


def report_data(project_id: int | None, user_id: int, headline: str) -> dict:
    """Возвращает поля аналитического свода для сохранения."""
    return {
        "project_id": project_id,
        "created_by_user_id": user_id,
        "created_by_display_name_snapshot": "Владельцев Виктор",
        "llm_model": "test-model",
        "duration_ms": 1200,
        "payload": {"headline": headline, "findings": []},
        "context_summary": {"projects": 1, "truncated": False},
    }


@pytest.mark.asyncio
async def test_get_latest_for_project_returns_last_saved_report(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    repository = AnalyticsReportsRepository(db_session)
    await repository.save(report_data(project.id, user.id, "первый"))
    await repository.save(report_data(project.id, user.id, "второй"))

    latest = await repository.get_latest_for_project(project_id=project.id)

    assert latest is not None
    assert latest.payload["headline"] == "второй"
    assert latest.project.key == project.key


@pytest.mark.asyncio
async def test_get_latest_for_project_ignores_portfolio_reports(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    repository = AnalyticsReportsRepository(db_session)
    await repository.save(report_data(None, user.id, "портфель"))

    assert await repository.get_latest_for_project(project_id=project.id) is None


@pytest.mark.asyncio
async def test_get_latest_portfolio_is_isolated_by_author(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    other = await UsersRepository(db_session).save(
        data={
            "username": "other",
            "password_hash": "hash",
            "last_name": "Другов",
            "first_name": "Дмитрий",
            "is_active": True,
        }
    )
    repository = AnalyticsReportsRepository(db_session)
    await repository.save(report_data(None, other.id, "чужой портфель"))

    assert await repository.get_latest_portfolio(user_id=user.id) is None
    own = await repository.get_latest_portfolio(user_id=other.id)
    assert own is not None
    assert own.payload["headline"] == "чужой портфель"


@pytest.mark.asyncio
async def test_saved_report_keeps_jsonb_payload_shape(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    repository = AnalyticsReportsRepository(db_session)

    saved = await repository.save(
        {
            **report_data(project.id, user.id, "свод"),
            "payload": {
                "headline": "свод",
                "findings": [{"kind": "OVERDUE", "tasks": [{"id": 1, "key": "PROJ-1"}]}],
            },
        }
    )

    stored = await repository.get_latest_for_project(project_id=project.id)
    assert stored is not None
    assert stored.id == saved.id
    assert stored.payload["findings"][0]["tasks"][0]["key"] == "PROJ-1"
