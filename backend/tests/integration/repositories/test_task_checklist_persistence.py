"""Атомарность чек-листа задачи на настоящем PostgreSQL."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.db.models.knowledge_index_jobs import KnowledgeIndexJob
from src.db.models.project_members import ProjectMember
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.task_activity import TaskActivity
from src.db.models.tasks import Task
from src.db.models.users import User
from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.tasks import TaskChecklistConflictError, TasksServiceError
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.task_participants import TaskParticipantsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.knowledge_events import KnowledgeEvents
from src.services.tasks import TasksService
from src.storage.task_attachments import TaskAttachmentStorage
from tests.unit.services.test_task_checklists import checklist


def build_service(session, tmp_path):
    return TasksService(
        tasks_repository=TasksRepository(session),
        members_repository=ProjectMembersRepository(session),
        participants_repository=TaskParticipantsRepository(session),
        projects_repository=ProjectsRepository(session),
        stages_repository=ProjectStagesRepository(session),
        comments_repository=TaskCommentsRepository(session),
        activity_repository=TaskActivityRepository(session),
        wbs_nodes_repository=WbsNodesRepository(session),
        unit_of_work=UnitOfWork(session),
        attachment_storage=TaskAttachmentStorage(tmp_path),
        knowledge_events=KnowledgeEvents(
            repository=KnowledgeIndexJobsRepository(session), enabled=True
        ),
    )


async def test_task_checklist_crud_and_history_and_outbox_are_atomic(
    db_session, project, stage, user, tmp_path
):
    db_session.add(ProjectMember(project_id=project.id, user_id=user.id, role="OWNER"))
    await db_session.flush()
    service = build_service(db_session, tmp_path)
    value = checklist()
    created = await service.create_task(
        project_id=project.id,
        data={"title": "Проверка запуска", "stage_id": stage.id, "checklist": value},
        created_by_user_id=user.id,
    )
    task_id = created.id
    assert created.checklist_revision == 1
    assert created.checklist.model_dump(mode="json") == value
    assert (await service.get_task(task_id)).checklist == created.checklist
    value["items"].reverse()
    value["items"][0]["is_completed"] = True
    updated = await service.update_task(
        task_id=task_id, data={"checklist": value, "checklist_revision": 1}
    )
    assert updated.checklist_revision == 2
    assert updated.checklist.items[0].is_completed
    assert str(updated.checklist.items[0].id) == value["items"][0]["id"]
    activities_before = (await db_session.execute(select(func.count(TaskActivity.id)))).scalar_one()
    jobs_before = (await db_session.execute(select(func.count(KnowledgeIndexJob.id)))).scalar_one()
    service.knowledge_events.upsert = AsyncMock(
        side_effect=KnowledgeEventsServiceError("outbox failed")
    )
    with pytest.raises(TasksServiceError):
        await service.update_task(
            task_id=task_id, data={"checklist": None, "checklist_revision": 2}
        )
    actual = await db_session.get(Task, task_id)
    assert actual.checklist == value and actual.checklist_revision == 2
    assert (
        await db_session.execute(select(func.count(TaskActivity.id)))
    ).scalar_one() == activities_before
    assert (
        await db_session.execute(select(func.count(KnowledgeIndexJob.id)))
    ).scalar_one() == jobs_before
    service = build_service(db_session, tmp_path)
    deleted = await service.update_task(
        task_id=task_id, data={"checklist": None, "checklist_revision": 2}
    )
    assert deleted.checklist is None and deleted.checklist_revision == 3
    recreated = await service.update_task(
        task_id=task_id, data={"checklist": checklist(), "checklist_revision": 3}
    )
    assert recreated.checklist_revision == 4
    assert len(recreated.checklist.items) == 2


async def test_stale_cache_and_concurrent_updates_do_not_overwrite_each_other(engine, tmp_path):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    marker = uuid4().hex[:8]
    async with factory() as session:
        user = User(
            username=f"checklist_{marker}", password_hash="!", first_name="Тест", last_name="Тест"
        )
        session.add(user)
        await session.flush()
        project = Project(
            owner_id=user.id,
            key=f"C{marker.upper()}",
            name="Версии",
            color="#334455",
            order_index=0,
        )
        session.add(project)
        await session.flush()
        stage = ProjectStage(project_id=project.id, name="Работа", color="#334455", order_index=0)
        session.add(stage)
        await session.flush()
        await session.commit()
        created = await build_service(session, tmp_path).create_task(
            project_id=project.id,
            data={"title": "Версии", "stage_id": stage.id, "checklist": checklist()},
        )
        task_id, project_id, user_id = created.id, project.id, user.id
    try:
        async with factory() as reader:
            cached = await reader.get(Task, task_id)
            async with factory() as writer:
                await build_service(writer, tmp_path).update_task(
                    task_id=task_id,
                    data={"checklist": None, "checklist_revision": 1},
                )
            assert cached.checklist_revision == 1
            with pytest.raises(TaskChecklistConflictError):
                await build_service(reader, tmp_path).update_task(
                    task_id=task_id,
                    data={"checklist": checklist(), "checklist_revision": 1},
                )
            actual = await reader.get(Task, task_id)
            assert actual.checklist is None and actual.checklist_revision == 2

        async def change(title):
            # У конкурирующих операций разные соединения, как у HTTP-запросов.
            async with factory() as session:
                value = checklist()
                value["title"] = title
                return await build_service(session, tmp_path).update_task(
                    task_id=task_id,
                    data={"checklist": value, "checklist_revision": 2},
                )

        results = await asyncio.gather(change("Первый"), change("Второй"), return_exceptions=True)
        assert sum(isinstance(result, TaskChecklistConflictError) for result in results) == 1
        assert sum(not isinstance(result, BaseException) for result in results) == 1
        async with factory() as session:
            actual = await session.get(Task, task_id)
            assert actual.checklist_revision == 3
            assert actual.checklist["title"] in {"Первый", "Второй"}
    finally:
        # Удаляются только записи этого теста в контейнере тестового PostgreSQL.
        async with factory() as session:
            await session.execute(delete(Project).where(Project.id == project_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
