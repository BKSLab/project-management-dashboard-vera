"""Паспорт, команда, стадии, FTS и история проходят общий сценарий в PostgreSQL."""

from datetime import date
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.projects import ProjectsServiceError, ProjectValidationError
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.project_deadline_changes import ProjectDeadlineChangesRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.users import UsersRepository
from src.schemas.projects import ProjectCreateSchema
from src.services.knowledge_events import KnowledgeEvents
from src.services.project_stages import ProjectStagesService
from src.services.projects import ProjectsService


def project_service(session):
    return ProjectsService(
        projects_repository=ProjectsRepository(session),
        members_repository=ProjectMembersRepository(session),
        stages_repository=ProjectStagesRepository(session),
        tasks_repository=TasksRepository(session),
        unit_of_work=UnitOfWork(session),
        attachment_storage=None,
        users_repository=UsersRepository(session),
        deadline_changes_repository=ProjectDeadlineChangesRepository(session),
        knowledge_events=KnowledgeEvents(KnowledgeIndexJobsRepository(session)),
    )


async def test_create_passport_team_stages_and_search_then_review_deadline(db_session, user):
    service = project_service(db_session)
    await UsersRepository(db_session).save(
        data={
            "username": "anna",
            "password_hash": "!",
            "first_name": "Анна",
            "last_name": "Тестова",
            "is_active": True,
        }
    )
    project = await service.create_project(
        ProjectCreateSchema.model_validate(
            {
                "key": "PAS",
                "name": "Паспорт",
                "start_date": "2026-09-01",
                "due_date": "2026-10-01",
                "member_usernames": ["anna", "owner"],
                "description_sections": {"goal": "Автоматизация приёмки"},
                "stages": [
                    {"name": "Входящие"},
                    {"name": "Проверка"},
                    {"name": "Принято", "is_done_stage": True},
                ],
            }
        ).model_dump(),
        user.id,
    )
    assert project.owner_id == user.id
    assert project.description_md == "## Цель\n\nАвтоматизация приёмки"
    members = await service.members_repository.get_for_project(project.id)
    assert {member.user.username for member in members} == {"owner", "anna"}
    stages = await service.stages_repository.get_by_project(project.id)
    assert [stage.name for stage in stages] == ["Входящие", "Проверка", "Принято"]
    assert await db_session.scalar(
        text(
            "SELECT search_vector @@ plainto_tsquery('russian', 'автоматизация') FROM projects WHERE id=:id"
        ),
        {"id": project.id},
    )
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM knowledge_index_jobs WHERE project_id=:id"),
            {"id": project.id},
        )
        == 1
    )

    with pytest.raises(ProjectValidationError):
        await service.update_project(project.id, {"due_date": None}, user.id)
    owner_id = project.owner_id
    await service.update_project(
        project.id, {"due_date": None, "due_date_comment": "  Перепланирование  "}, owner_id
    )
    with pytest.raises(ProjectValidationError):
        await service.update_project(project.id, {"due_date": date(2026, 11, 1)}, owner_id)
    await service.update_project(
        project.id, {"due_date": date(2026, 11, 1), "due_date_comment": "План согласован"}, owner_id
    )
    history = await service.get_deadline_history(project.id)
    assert [(row.previous_due_date, row.new_due_date, row.comment) for row in history] == [
        (None, date(2026, 11, 1), "План согласован"),
        (date(2026, 10, 1), None, "Перепланирование"),
        (None, date(2026, 10, 1), None),
    ]
    assert all(
        row.changed_by_name == "Владельцев Виктор" and row.created_at.tzinfo for row in history
    )


async def test_outbox_failure_rolls_back_both_deadline_and_its_history(db_session, user):
    service = project_service(db_session)
    project = await service.create_project(
        {
            "key": "ATOMIC",
            "name": "Транзакция",
            "color": "#58a6ff",
            "start_date": date(2026, 9, 1),
            "due_date": date(2026, 10, 1),
        },
        user.id,
    )
    service.knowledge_events = AsyncMock(spec=KnowledgeEvents)
    service.knowledge_events.upsert.side_effect = KnowledgeEventsServiceError("Outbox недоступен")
    with pytest.raises(ProjectsServiceError):
        await service.update_project(
            project.id,
            {
                "due_date": date(2026, 11, 1),
                "due_date_comment": "Перенос",
                "description_sections": {"goal": "Изменённая цель"},
            },
            user.id,
        )
    saved = await service.get_project(project.id)
    assert saved.due_date == date(2026, 10, 1)
    assert saved.description_md is None
    assert len(await service.get_deadline_history(project.id)) == 1


async def test_stage_reordering_is_scoped_to_project_and_preserves_tasks(db_session, user):
    service = project_service(db_session)
    first = await service.create_project(
        {"key": "FIRST", "name": "Первый", "color": "#58a6ff"}, user.id
    )
    second = await service.create_project(
        {"key": "SECOND", "name": "Второй", "color": "#58a6ff"}, user.id
    )
    stages = await service.stages_repository.get_by_project(first.id)
    task = await service.tasks_repository.save(
        data={
            "project_id": first.id,
            "stage_id": stages[0].id,
            "number": 1,
            "title": "Задача в первой стадии",
            "position": 1000,
        }
    )
    task_id, stage_id = task.id, stages[0].id
    stage_service = ProjectStagesService(
        service.stages_repository,
        service.projects_repository,
        service.tasks_repository,
        service.unit_of_work,
    )
    await stage_service.update_stage(stage_id, {"order_index": len(stages) - 1})
    moved = await service.stages_repository.get_by_project(first.id)
    assert moved[-1].id == stage_id
    assert [stage.order_index for stage in moved] == list(range(len(stages)))
    assert (await service.tasks_repository.get_by_id(task_id)).stage_id == stage_id
    other = await service.stages_repository.get_by_project(second.id)
    assert other[0].name == "Бэклог"
    assert [stage.order_index for stage in other] == list(range(len(stages)))
