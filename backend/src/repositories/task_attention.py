"""Чтение версий и монотонная фиксация персонального просмотра."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_members import ProjectMember
from src.db.models.project_stages import ProjectStage
from src.db.models.task_participants import TaskParticipant
from src.db.models.task_views import TaskView
from src.db.models.tasks import Task
from src.exceptions.task_attention import TaskAttentionRepositoryError
from src.schemas.enums import TaskStatus


class TaskAttentionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_rows(self, *, user_id: int, task_id: int | None = None) -> list[dict]:
        """Читает полные персональные версии, без ограничения списка задач в UI."""
        participation = (
            select(TaskParticipant.task_id)
            .outerjoin(ProjectMember, ProjectMember.id == TaskParticipant.project_member_id)
            .where(func.coalesce(TaskParticipant.user_id, ProjectMember.user_id) == user_id)
        )
        closed = or_(
            Task.status.in_((TaskStatus.DONE, TaskStatus.CANCELLED)),
            ProjectStage.is_done_stage.is_(True),
        )
        statement = (
            select(
                Task.id.label("task_id"),
                Task.attention_revision.label("revision"),
                Task.attention_deadline_revision.label("deadline_revision"),
                Task.due_date,
                func.coalesce(closed, False).label("closed"),
                TaskView.revision.label("seen_revision"),
                TaskView.deadline_revision.label("seen_deadline_revision"),
            )
            .outerjoin(ProjectStage, ProjectStage.id == Task.stage_id)
            .outerjoin(TaskView, and_(TaskView.task_id == Task.id, TaskView.user_id == user_id))
            .where(Task.id == task_id if task_id is not None else Task.id.in_(participation))
            .order_by(Task.id)
        )
        try:
            result = await self.session.execute(statement)
            return [dict(row) for row in result.mappings()]
        except SQLAlchemyError as error:
            await self.session.rollback()
            raise TaskAttentionRepositoryError(str(error)) from error

    async def mark_viewed(
        self, *, user_id: int, task_id: int, revision: int, deadline_revision: int
    ) -> None:
        """Обновляет только подтверждённые версии; запоздалые запросы не уменьшают их."""
        statement = insert(TaskView).values(
            user_id=user_id,
            task_id=task_id,
            revision=revision,
            deadline_revision=deadline_revision,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[TaskView.user_id, TaskView.task_id],
            set_={
                "revision": func.greatest(TaskView.revision, statement.excluded.revision),
                "deadline_revision": func.greatest(
                    TaskView.deadline_revision, statement.excluded.deadline_revision
                ),
            },
            where=or_(TaskView.revision < revision, TaskView.deadline_revision < deadline_revision),
        )
        try:
            await self.session.execute(statement)
        except SQLAlchemyError as error:
            await self.session.rollback()
            raise TaskAttentionRepositoryError(str(error)) from error
