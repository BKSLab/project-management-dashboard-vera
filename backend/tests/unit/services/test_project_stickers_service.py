from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.project_stickers import ProjectStickerColor
from src.db.models.users import User
from src.exceptions.project_stickers import (
    ProjectStickerNotFoundError,
    ProjectStickerRevisionConflictError,
    ProjectStickersRepositoryError,
    ProjectStickersServiceError,
    ProjectStickerTaskMismatchError,
)
from src.repositories.project_stickers import ProjectStickersRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.project_stickers import (
    ProjectStickerCreateSchema,
    ProjectStickerPositionUpdateSchema,
    ProjectStickerUpdateSchema,
)
from src.services.project_stickers import ProjectStickersService


def sticker(*, revision: int = 1, task_ids: list[int] | None = None) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=4,
        project_id=1,
        body="Согласовать API",
        color=ProjectStickerColor.YELLOW,
        canvas_x=40.0,
        canvas_y=40.0,
        created_by_user_id=7,
        created_by_username_snapshot="vera",
        created_by_display_name_snapshot="Иванова Вера",
        task_links=[SimpleNamespace(task_id=task_id) for task_id in (task_ids or [])],
        revision=revision,
        created_at=now,
        updated_at=now,
    )


def user() -> User:
    return User(
        id=7,
        username="vera",
        password_hash="hash",
        last_name="Иванова",
        first_name="Вера",
        middle_name="Петровна",
        is_active=True,
    )


def service(
    repository: AsyncMock | None = None,
    tasks_repository: AsyncMock | None = None,
    unit_of_work: AsyncMock | None = None,
) -> ProjectStickersService:
    return ProjectStickersService(
        stickers_repository=repository or AsyncMock(spec=ProjectStickersRepository),
        tasks_repository=tasks_repository or AsyncMock(spec=TasksRepository),
        unit_of_work=unit_of_work or AsyncMock(spec=UnitOfWork),
    )


@pytest.mark.asyncio
async def test_list_returns_transport_contract() -> None:
    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.list_by_project_id.return_value = [sticker(task_ids=[11, 12])]

    result = await service(repository).list_stickers(project_id=1)

    assert result[0].task_ids == [11, 12]
    repository.list_by_project_id.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_stale_revision_never_overwrites_someone_elses_change() -> None:
    """Устаревшая ревизия отклоняется и до записи, и по её результату.

    Проверка перед записью ловит явно старую версию, а нулевое число
    затронутых строк — гонку двух одновременных правок. Оба случая для
    клиента одинаковы: его версия больше не актуальна.
    """
    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.get_by_id.return_value = sticker(revision=5)
    with pytest.raises(ProjectStickerRevisionConflictError):
        await service(repository).update_sticker(
            project_id=1,
            sticker_id=4,
            data=ProjectStickerUpdateSchema(revision=4, body="Поздняя версия"),
        )
    repository.update_fields.assert_not_awaited()

    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.get_by_id.return_value = sticker(revision=2)
    repository.update_fields.return_value = False
    with pytest.raises(ProjectStickerRevisionConflictError):
        await service(repository).update_sticker(
            project_id=1,
            sticker_id=4,
            data=ProjectStickerUpdateSchema(revision=2, color="green"),
        )

    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.get_by_id.return_value = sticker(revision=3)
    repository.delete.return_value = False
    with pytest.raises(ProjectStickerRevisionConflictError):
        await service(repository).delete_sticker(project_id=1, sticker_id=4, revision=3)


@pytest.mark.asyncio
async def test_missing_sticker_is_not_found_on_update_and_move() -> None:
    """Отсутствующий стикер отвечает 404, а не конфликтом ревизии."""
    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.get_by_id.return_value = None
    with pytest.raises(ProjectStickerNotFoundError):
        await service(repository).update_sticker(
            project_id=1,
            sticker_id=404,
            data=ProjectStickerUpdateSchema(revision=1, body="Текст"),
        )

    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.update_position.return_value = False
    with pytest.raises(ProjectStickerNotFoundError):
        await service(repository).move_sticker(
            project_id=1,
            sticker_id=404,
            data=ProjectStickerPositionUpdateSchema(canvas_x=10.0, canvas_y=20.0),
        )


@pytest.mark.asyncio
async def test_move_updates_only_canvas_position_and_commits() -> None:
    repository = AsyncMock(spec=ProjectStickersRepository)
    moved = sticker(revision=3)
    moved.canvas_x = 312.5
    moved.canvas_y = -48.0
    repository.update_position.return_value = True
    repository.get_by_id.return_value = moved
    unit_of_work = AsyncMock(spec=UnitOfWork)

    result = await service(repository, unit_of_work=unit_of_work).move_sticker(
        project_id=1,
        sticker_id=4,
        data=ProjectStickerPositionUpdateSchema(canvas_x=312.5, canvas_y=-48.0),
    )

    assert result.canvas_x == 312.5
    assert result.canvas_y == -48.0
    assert result.revision == 3
    repository.update_position.assert_awaited_once_with(
        project_id=1,
        sticker_id=4,
        canvas_x=312.5,
        canvas_y=-48.0,
    )
    unit_of_work.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_uses_revision_and_commits() -> None:
    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.get_by_id.return_value = sticker(revision=3)
    repository.delete.return_value = True
    unit_of_work = AsyncMock(spec=UnitOfWork)

    await service(repository, unit_of_work=unit_of_work).delete_sticker(
        project_id=1,
        sticker_id=4,
        revision=3,
    )

    repository.delete.assert_awaited_once_with(
        project_id=1,
        sticker_id=4,
        expected_revision=3,
    )
    unit_of_work.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_repository_failure_is_wrapped() -> None:
    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.list_by_project_id.side_effect = ProjectStickersRepositoryError("БД недоступна")

    with pytest.raises(ProjectStickersServiceError):
        await service(repository).list_stickers(project_id=1)


@pytest.mark.asyncio
async def test_sticker_create_and_update_preserve_author_and_links() -> None:
    """Автор проставляется по сессии и сохраняется при правке, связи задач заменяются, чужая задача отклоняется."""

    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.insert.return_value = 4
    repository.get_by_id.return_value = sticker(task_ids=[11])
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_project.return_value = [SimpleNamespace(id=11)]
    unit_of_work = AsyncMock(spec=UnitOfWork)

    result = await service(repository, tasks_repository, unit_of_work).create_sticker(
        project_id=1,
        data=ProjectStickerCreateSchema(body="  Согласовать API  ", task_ids=[11]),
        author_id=user().id,
        author_username=user().username,
        author_display_name="Иванова Вера Петровна",
    )

    assert result.id == 4
    saved = repository.insert.await_args.kwargs
    assert saved["data"]["created_by_user_id"] == 7
    assert saved["data"]["created_by_username_snapshot"] == "vera"
    assert saved["data"]["created_by_display_name_snapshot"] == "Иванова Вера Петровна"
    assert saved["data"]["body"] == "Согласовать API"
    assert saved["data"]["canvas_x"] == 40.0
    assert saved["data"]["canvas_y"] == 40.0
    links = repository.replace_task_links.await_args.kwargs
    assert links["task_ids"] == [11]
    unit_of_work.commit.assert_awaited_once_with()

    repository = AsyncMock(spec=ProjectStickersRepository)
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_project.return_value = []

    with pytest.raises(ProjectStickerTaskMismatchError):
        await service(repository, tasks_repository).create_sticker(
            project_id=1,
            data=ProjectStickerCreateSchema(body="Текст", task_ids=[99]),
            author_id=user().id,
        author_username=user().username,
        author_display_name="Иванова Вера Петровна",
        )

    repository.insert.assert_not_awaited()

    repository = AsyncMock(spec=ProjectStickersRepository)
    repository.get_by_id.side_effect = [
        sticker(revision=3, task_ids=[11]),
        sticker(revision=4, task_ids=[12]),
    ]
    repository.update_fields.return_value = True
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_project.return_value = [SimpleNamespace(id=12)]
    unit_of_work = AsyncMock(spec=UnitOfWork)

    result = await service(repository, tasks_repository, unit_of_work).update_sticker(
        project_id=1,
        sticker_id=4,
        data=ProjectStickerUpdateSchema(
            revision=3,
            body="Новый текст",
            color="blue",
            task_ids=[12],
        ),
    )

    assert result.revision == 4
    changes = repository.update_fields.await_args.kwargs
    assert changes["expected_revision"] == 3
    assert changes["changes"] == {
        "body": "Новый текст",
        "color": ProjectStickerColor.BLUE,
    }
    assert repository.replace_task_links.await_args.kwargs["task_ids"] == [12]
    assert "created_by_user_id" not in changes["changes"]
    unit_of_work.commit.assert_awaited_once_with()
