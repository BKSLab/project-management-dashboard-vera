import logging

from src.db.models.project_stickers import ProjectSticker
from src.exceptions.project_stickers import (
    ProjectStickerNotFoundError,
    ProjectStickerRevisionConflictError,
    ProjectStickersRepositoryError,
    ProjectStickersServiceError,
    ProjectStickerTaskMismatchError,
)
from src.exceptions.tasks import TasksRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.repositories.project_stickers import ProjectStickersRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.project_stickers import (
    ProjectStickerCreateSchema,
    ProjectStickerPositionUpdateSchema,
    ProjectStickerSchema,
    ProjectStickerUpdateSchema,
)

logger = logging.getLogger(__name__)
RepositoryErrors = (
    ProjectStickersRepositoryError,
    TasksRepositoryError,
    UnitOfWorkRepositoryError,
)


class ProjectStickersService:
    """CRUD стикеров, авторство и безопасные связи с задачами проекта."""

    def __init__(
        self,
        *,
        stickers_repository: ProjectStickersRepository,
        tasks_repository: TasksRepository,
        unit_of_work: UnitOfWork,
    ):
        self.stickers_repository = stickers_repository
        self.tasks_repository = tasks_repository
        self.unit_of_work = unit_of_work

    async def list_stickers(self, project_id: int) -> list[ProjectStickerSchema]:
        """Возвращает общую доску стикеров проекта."""
        try:
            stickers = await self.stickers_repository.list_by_project_id(project_id)
            return [_to_sticker_schema(sticker) for sticker in stickers]
        except RepositoryErrors as error:
            logger.error(
                "❌ Ошибка получения стикеров проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise ProjectStickersServiceError(str(error)) from error

    async def create_sticker(
        self,
        *,
        project_id: int,
        data: ProjectStickerCreateSchema,
        author_id: int,
        author_username: str,
        author_display_name: str,
    ) -> ProjectStickerSchema:
        """Создаёт стикер с неизменяемым снимком автора."""
        try:
            await self._validate_task_ids(project_id, data.task_ids)
            sticker = await self.stickers_repository.create(
                data={
                    "project_id": project_id,
                    "body": data.body,
                    "color": data.color,
                    "canvas_x": data.canvas_x,
                    "canvas_y": data.canvas_y,
                    "created_by_user_id": author_id,
                    "created_by_username_snapshot": author_username,
                    "created_by_display_name_snapshot": author_display_name,
                },
                task_ids=data.task_ids,
            )
            await self.unit_of_work.commit()
            return _to_sticker_schema(sticker)
        except RepositoryErrors as error:
            logger.error(
                "❌ Ошибка создания стикера проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise ProjectStickersServiceError(str(error)) from error

    async def move_sticker(
        self,
        *,
        project_id: int,
        sticker_id: int,
        data: ProjectStickerPositionUpdateSchema,
    ) -> ProjectStickerSchema:
        """Сохраняет положение стикера отдельно от версии его содержимого."""
        try:
            moved = await self.stickers_repository.update_position(
                project_id=project_id,
                sticker_id=sticker_id,
                canvas_x=data.canvas_x,
                canvas_y=data.canvas_y,
            )
            if moved is None:
                raise ProjectStickerNotFoundError(sticker_id)
            await self.unit_of_work.commit()
            return _to_sticker_schema(moved)
        except RepositoryErrors as error:
            logger.error("❌ Ошибка перемещения стикера id=%s.", sticker_id, exc_info=True)
            raise ProjectStickersServiceError(str(error)) from error

    async def update_sticker(
        self,
        *,
        project_id: int,
        sticker_id: int,
        data: ProjectStickerUpdateSchema,
    ) -> ProjectStickerSchema:
        """Изменяет текст, цвет или задачи, не меняя автора стикера."""
        try:
            current = await self.stickers_repository.get_by_id(
                project_id=project_id,
                sticker_id=sticker_id,
            )
            if current is None:
                raise ProjectStickerNotFoundError(sticker_id)
            if current.revision != data.revision:
                raise ProjectStickerRevisionConflictError(sticker_id, data.revision)

            task_ids = data.task_ids if "task_ids" in data.model_fields_set else None
            if task_ids is not None:
                await self._validate_task_ids(project_id, task_ids)
            changes = data.model_dump(
                exclude={"revision", "task_ids"},
                exclude_unset=True,
            )
            updated = await self.stickers_repository.update(
                project_id=project_id,
                sticker_id=sticker_id,
                expected_revision=data.revision,
                changes=changes,
                task_ids=task_ids,
            )
            if updated is None:
                raise ProjectStickerRevisionConflictError(sticker_id, data.revision)
            await self.unit_of_work.commit()
            return _to_sticker_schema(updated)
        except RepositoryErrors as error:
            logger.error("❌ Ошибка изменения стикера id=%s.", sticker_id, exc_info=True)
            raise ProjectStickersServiceError(str(error)) from error

    async def delete_sticker(
        self,
        *,
        project_id: int,
        sticker_id: int,
        revision: int,
    ) -> None:
        """Удаляет стикер по актуальной ревизии."""
        try:
            current = await self.stickers_repository.get_by_id(
                project_id=project_id,
                sticker_id=sticker_id,
            )
            if current is None:
                raise ProjectStickerNotFoundError(sticker_id)
            if current.revision != revision:
                raise ProjectStickerRevisionConflictError(sticker_id, revision)
            deleted = await self.stickers_repository.delete(
                project_id=project_id,
                sticker_id=sticker_id,
                expected_revision=revision,
            )
            if not deleted:
                raise ProjectStickerRevisionConflictError(sticker_id, revision)
            await self.unit_of_work.commit()
        except RepositoryErrors as error:
            logger.error("❌ Ошибка удаления стикера id=%s.", sticker_id, exc_info=True)
            raise ProjectStickersServiceError(str(error)) from error

    async def _validate_task_ids(self, project_id: int, task_ids: list[int]) -> None:
        """Не позволяет ссылаться на отсутствующие или чужие задачи."""
        requested = set(task_ids)
        if not requested:
            return
        tasks = await self.tasks_repository.get_by_project(
            project_id=project_id,
            task_ids=requested,
        )
        found = {task.id for task in tasks}
        if found != requested:
            raise ProjectStickerTaskMismatchError(requested - found)


def _to_sticker_schema(sticker: ProjectSticker) -> ProjectStickerSchema:
    """Преобразует ORM-сущность в безопасный transport contract."""
    return ProjectStickerSchema(
        id=sticker.id,
        project_id=sticker.project_id,
        body=sticker.body,
        color=sticker.color,
        canvas_x=sticker.canvas_x,
        canvas_y=sticker.canvas_y,
        created_by_user_id=sticker.created_by_user_id,
        created_by_username_snapshot=sticker.created_by_username_snapshot,
        created_by_display_name_snapshot=sticker.created_by_display_name_snapshot,
        task_ids=[link.task_id for link in sticker.task_links],
        revision=sticker.revision,
        created_at=sticker.created_at,
        updated_at=sticker.updated_at,
    )
