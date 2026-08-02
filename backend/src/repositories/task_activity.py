import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.task_activity import TaskActivity, TaskActivityEventType
from src.exceptions.task_activity import TaskActivityRepositoryError

logger = logging.getLogger(__name__)


class TaskActivityRepository:
    """Репозиторий неизменяемой истории задач."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_for_task(self, task_id: int) -> list[TaskActivity]:
        """Возвращает историю задачи в хронологическом порядке.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            События истории задачи.

        Raises:
            TaskActivityRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(TaskActivity)
                .where(TaskActivity.task_id == task_id)
                .order_by(TaskActivity.created_at)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить историю задачи id=%s.", task_id, exc_info=True)
            raise TaskActivityRepositoryError(
                f"Ошибка получения истории задачи id={task_id}."
            ) from error

    async def save(
        self,
        task_id: int,
        event_type: TaskActivityEventType,
        from_value: str | None,
        to_value: str | None,
    ) -> TaskActivity:
        """Сохраняет событие истории задачи.

        Args:
            task_id: Идентификатор задачи.
            event_type: Тип события.
            from_value: Предыдущее значение.
            to_value: Новое значение.

        Returns:
            Сохранённое событие.

        Raises:
            TaskActivityRepositoryError: Если сохранить событие не удалось.
        """
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
            logger.error("❌ Не удалось сохранить историю задачи id=%s.", task_id, exc_info=True)
            raise TaskActivityRepositoryError(
                f"Ошибка сохранения истории задачи id={task_id}."
            ) from error
