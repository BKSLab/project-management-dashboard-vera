import logging
from collections import defaultdict

from sqlalchemy import Result, delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.db.models.project_members import ProjectMember
from src.db.models.task_participants import TaskParticipant, TaskParticipantRole
from src.exceptions.tasks import TasksRepositoryError

logger = logging.getLogger(__name__)


class TaskParticipantsRepository:
    """Репозиторий ролевых назначений членов команды на задачи."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_task_ids(
        self,
        task_ids: list[int],
    ) -> dict[int, list[TaskParticipant]]:
        """Возвращает назначения задач вместе с безопасной идентичностью пользователей."""
        if not task_ids:
            return {}
        try:
            result: Result = await self.db_session.execute(
                select(TaskParticipant)
                .options(
                    joinedload(TaskParticipant.project_member).joinedload(ProjectMember.user)
                )
                .where(TaskParticipant.task_id.in_(task_ids))
                .order_by(TaskParticipant.task_id, TaskParticipant.id)
            )
            grouped: defaultdict[int, list[TaskParticipant]] = defaultdict(list)
            for participant in result.scalars().all():
                grouped[participant.task_id].append(participant)
            return dict(grouped)
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить участников задач.", exc_info=True)
            raise TasksRepositoryError("Ошибка получения участников задач.") from error

    async def get_for_project_member(
        self,
        project_member_id: int,
        role: TaskParticipantRole | None = None,
    ) -> list[TaskParticipant]:
        """Возвращает назначения конкретного члена проектной команды."""
        try:
            stmt = select(TaskParticipant).where(
                TaskParticipant.project_member_id == project_member_id
            )
            if role is not None:
                stmt = stmt.where(TaskParticipant.role == role)
            result: Result = await self.db_session.execute(stmt.order_by(TaskParticipant.id))
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить назначения участника проекта id=%s.",
                project_member_id,
                exc_info=True,
            )
            raise TasksRepositoryError("Ошибка получения назначений участника.") from error

    async def replace_for_task(self, task_id: int, assignments: list[dict]) -> None:
        """Атомарно заменяет полный набор ролевых назначений задачи."""
        try:
            await self.db_session.execute(
                delete(TaskParticipant).where(TaskParticipant.task_id == task_id)
            )
            await self.db_session.flush()
            if assignments:
                self.db_session.add_all(
                    [
                        TaskParticipant(task_id=task_id, **assignment)
                        for assignment in assignments
                    ]
                )
                await self.db_session.flush()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось заменить участников задачи id=%s.",
                task_id,
                exc_info=True,
            )
            raise TasksRepositoryError("Ошибка сохранения участников задачи.") from error
