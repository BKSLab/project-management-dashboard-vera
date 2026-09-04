import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.db.models.project_stickers import (
    ProjectSticker,
    ProjectStickerColor,
    ProjectStickerTaskLink,
)
from src.db.models.projects import Project
from src.db.models.tasks import Task, TaskPriority
from src.db.models.users import User
from src.repositories.project_stickers import ProjectStickersRepository


async def create_task(
    db_session: AsyncSession,
    *,
    project: Project,
    stage: ProjectStage,
    number: int,
) -> Task:
    task = Task(
        project_id=project.id,
        stage_id=stage.id,
        number=number,
        title=f"Задача {number}",
        priority=TaskPriority.MEDIUM,
        position=float(number),
    )
    db_session.add(task)
    await db_session.flush()
    return task


async def create_sticker(
    repository: ProjectStickersRepository,
    *,
    project: Project,
    user: User,
    task_ids: list[int],
) -> ProjectSticker:
    return await repository.create(
        data={
            "project_id": project.id,
            "body": "Согласовать API",
            "color": ProjectStickerColor.YELLOW,
            "created_by_user_id": user.id,
            "created_by_username_snapshot": user.username,
            "created_by_display_name_snapshot": f"{user.last_name} {user.first_name}",
        },
        task_ids=task_ids,
    )


@pytest.mark.asyncio
async def test_crud_roundtrip_and_task_links(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    user: User,
) -> None:
    repository = ProjectStickersRepository(db_session)
    first = await create_task(db_session, project=project, stage=stage, number=1)
    second = await create_task(db_session, project=project, stage=stage, number=2)
    created = await create_sticker(
        repository,
        project=project,
        user=user,
        task_ids=[first.id],
    )

    listed = await repository.list_by_project_id(project.id)
    updated = await repository.update(
        project_id=project.id,
        sticker_id=created.id,
        expected_revision=1,
        changes={"body": "Новый текст", "color": ProjectStickerColor.BLUE},
        task_ids=[second.id],
    )
    stale = await repository.update(
        project_id=project.id,
        sticker_id=created.id,
        expected_revision=1,
        changes={"body": "Устаревший текст"},
        task_ids=None,
    )

    assert [item.id for item in listed] == [created.id]
    assert updated is not None
    assert updated.body == "Новый текст"
    assert updated.color is ProjectStickerColor.BLUE
    assert updated.revision == 2
    assert [link.task_id for link in updated.task_links] == [second.id]
    assert stale is None


@pytest.mark.asyncio
async def test_delete_is_revision_guarded(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    repository = ProjectStickersRepository(db_session)
    created = await create_sticker(repository, project=project, user=user, task_ids=[])

    assert (
        await repository.delete(
            project_id=project.id,
            sticker_id=created.id,
            expected_revision=2,
        )
        is False
    )
    assert (
        await repository.delete(
            project_id=project.id,
            sticker_id=created.id,
            expected_revision=1,
        )
        is True
    )
    assert await repository.get_by_id(project_id=project.id, sticker_id=created.id) is None


@pytest.mark.asyncio
async def test_position_update_preserves_content_revision_and_timestamp(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    repository = ProjectStickersRepository(db_session)
    created = await create_sticker(repository, project=project, user=user, task_ids=[])
    original_updated_at = created.updated_at

    moved = await repository.update_position(
        project_id=project.id,
        sticker_id=created.id,
        canvas_x=318.25,
        canvas_y=-72.5,
    )

    assert moved is not None
    assert moved.canvas_x == 318.25
    assert moved.canvas_y == -72.5
    assert moved.revision == 1
    assert moved.updated_at == original_updated_at


@pytest.mark.asyncio
async def test_position_update_is_scoped_to_project(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    repository = ProjectStickersRepository(db_session)
    created = await create_sticker(repository, project=project, user=user, task_ids=[])

    moved = await repository.update_position(
        project_id=project.id + 999,
        sticker_id=created.id,
        canvas_x=100.0,
        canvas_y=100.0,
    )

    assert moved is None


@pytest.mark.asyncio
async def test_task_and_project_foreign_keys_cascade(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    user: User,
) -> None:
    repository = ProjectStickersRepository(db_session)
    task = await create_task(db_session, project=project, stage=stage, number=1)
    created = await create_sticker(
        repository,
        project=project,
        user=user,
        task_ids=[task.id],
    )
    sticker_id = created.id

    await db_session.execute(delete(Task).where(Task.id == task.id))
    await db_session.flush()
    links = await db_session.scalars(
        select(ProjectStickerTaskLink).where(ProjectStickerTaskLink.sticker_id == sticker_id)
    )
    assert list(links) == []
    assert await repository.get_by_id(project_id=project.id, sticker_id=sticker_id) is not None

    await db_session.execute(delete(Project).where(Project.id == project.id))
    await db_session.flush()
    db_session.expire_all()
    assert await db_session.get(ProjectSticker, sticker_id) is None


@pytest.mark.asyncio
async def test_author_snapshot_survives_user_deletion(
    db_session: AsyncSession,
    project: Project,
) -> None:
    author = User(
        username="former-author",
        password_hash="hash",
        last_name="Бывший",
        first_name="Участник",
        is_active=True,
    )
    db_session.add(author)
    await db_session.flush()
    repository = ProjectStickersRepository(db_session)
    created = await create_sticker(repository, project=project, user=author, task_ids=[])
    project_id = project.id
    sticker_id = created.id

    await db_session.execute(delete(User).where(User.id == author.id))
    await db_session.flush()
    db_session.expire_all()
    preserved = await repository.get_by_id(project_id=project_id, sticker_id=sticker_id)

    assert preserved is not None
    assert preserved.created_by_user_id is None
    assert preserved.created_by_username_snapshot == "former-author"
    assert preserved.created_by_display_name_snapshot == "Бывший Участник"
