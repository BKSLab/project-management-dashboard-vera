import logging

from sqlalchemy import Result, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.kanban import (
    KanbanStage,
    KanbanTask,
    TaskActivity,
    TaskActivityEventType,
    TaskComment,
)
from src.exceptions.repositories import KanbanRepositoryError

logger = logging.getLogger(__name__)


class KanbanRepository:
    """Репозиторий для работы с канбан-доской в базе данных."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    # --- Стадии ---

    async def get_all_stages(self) -> list[KanbanStage]:
        try:
            stmt = select(KanbanStage).order_by(KanbanStage.order_index)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(error_details="Ошибка при получении списка стадий.") from error

    async def get_stage_by_id(self, stage_id: int) -> KanbanStage | None:
        try:
            stmt = select(KanbanStage).where(KanbanStage.id == stage_id)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(error_details=f"Ошибка при получении стадии id={stage_id}.") from error

    async def count_tasks_in_stage(self, stage_id: int) -> int:
        try:
            stmt = select(func.count()).select_from(KanbanTask).where(KanbanTask.stage_id == stage_id)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one()
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(
                error_details=f"Ошибка при подсчёте задач в стадии id={stage_id}."
            ) from error

    async def create_stage(self, data: dict) -> KanbanStage:
        try:
            stage = KanbanStage(**data)
            self.db_session.add(stage)
            await self.db_session.commit()
            await self.db_session.refresh(stage)
            return stage
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(error_details="Ошибка при создании стадии.") from error

    async def update_stage(self, stage: KanbanStage, data: dict) -> KanbanStage:
        try:
            for field, value in data.items():
                setattr(stage, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(stage)
            return stage
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(error_details=f"Ошибка при обновлении стадии id={stage.id}.") from error

    async def delete_stage(self, stage: KanbanStage) -> None:
        try:
            await self.db_session.delete(stage)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(error_details=f"Ошибка при удалении стадии id={stage.id}.") from error

    # --- Задачи ---

    async def get_tasks(self, stage_id: int | None = None) -> list[KanbanTask]:
        try:
            stmt = select(KanbanTask).order_by(KanbanTask.position)
            if stage_id is not None:
                stmt = stmt.where(KanbanTask.stage_id == stage_id)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(error_details="Ошибка при получении списка задач.") from error

    async def get_task_by_id(self, task_id: int) -> KanbanTask | None:
        try:
            stmt = select(KanbanTask).where(KanbanTask.id == task_id)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(error_details=f"Ошибка при получении задачи id={task_id}.") from error

    async def create_task(self, data: dict) -> KanbanTask:
        try:
            task = KanbanTask(**data)
            self.db_session.add(task)
            await self.db_session.commit()
            await self.db_session.refresh(task)
            return task
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(error_details="Ошибка при создании задачи.") from error

    async def update_task(self, task: KanbanTask, data: dict) -> KanbanTask:
        try:
            for field, value in data.items():
                setattr(task, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(task)
            return task
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(error_details=f"Ошибка при обновлении задачи id={task.id}.") from error

    async def delete_task(self, task: KanbanTask) -> None:
        try:
            await self.db_session.delete(task)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(error_details=f"Ошибка при удалении задачи id={task.id}.") from error

    # --- Комментарии ---

    async def get_comments(self, task_id: int) -> list[TaskComment]:
        try:
            stmt = select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(
                error_details=f"Ошибка при получении комментариев задачи id={task_id}."
            ) from error

    async def get_all_comments(self) -> list[TaskComment]:
        try:
            stmt = select(TaskComment).order_by(TaskComment.task_id, TaskComment.created_at)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(error_details="Ошибка при получении всех комментариев.") from error

    async def get_comment_by_id(self, comment_id: int) -> TaskComment | None:
        try:
            stmt = select(TaskComment).where(TaskComment.id == comment_id)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(
                error_details=f"Ошибка при получении комментария id={comment_id}."
            ) from error

    async def create_comment(self, task_id: int, author_name: str | None, body_md: str) -> TaskComment:
        try:
            comment = TaskComment(task_id=task_id, author_name=author_name, body_md=body_md)
            self.db_session.add(comment)
            await self.db_session.commit()
            await self.db_session.refresh(comment)
            return comment
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(
                error_details=f"Ошибка при создании комментария к задаче id={task_id}."
            ) from error

    async def delete_comment(self, comment: TaskComment) -> None:
        try:
            await self.db_session.delete(comment)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(
                error_details=f"Ошибка при удалении комментария id={comment.id}."
            ) from error

    # --- История изменений ---

    async def get_activity(self, task_id: int) -> list[TaskActivity]:
        try:
            stmt = (
                select(TaskActivity)
                .where(TaskActivity.task_id == task_id)
                .order_by(TaskActivity.created_at)
            )
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise KanbanRepositoryError(
                error_details=f"Ошибка при получении истории задачи id={task_id}."
            ) from error

    async def create_activity(
        self,
        task_id: int,
        event_type: TaskActivityEventType,
        from_value: str | None,
        to_value: str | None,
    ) -> TaskActivity:
        try:
            activity = TaskActivity(
                task_id=task_id,
                event_type=event_type,
                from_value=from_value,
                to_value=to_value,
            )
            self.db_session.add(activity)
            await self.db_session.commit()
            await self.db_session.refresh(activity)
            return activity
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            raise KanbanRepositoryError(
                error_details=f"Ошибка при записи истории задачи id={task_id}."
            ) from error
