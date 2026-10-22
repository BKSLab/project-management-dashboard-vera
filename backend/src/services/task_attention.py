"""Персональные сигналы до просмотра, общие для всех интерфейсов."""

from datetime import UTC, date, datetime

from src.exceptions.task_attention import (
    TaskAttentionRepositoryError,
    TaskAttentionServiceError,
    TaskAttentionVersionError,
)
from src.exceptions.tasks import TaskNotFoundError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.repositories.task_attention import TaskAttentionRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.task_attention import TaskAttentionItem, TaskAttentionSnapshot, TaskViewSchema


def attention_item(row: dict, today: date) -> TaskAttentionItem:
    """Просмотр до дедлайна не подтверждает нарушение, которое ещё не наступило."""
    overdue = not row["closed"] and row["due_date"] is not None and row["due_date"] < today
    seen = row["seen_revision"]
    return TaskAttentionItem(
        task_id=row["task_id"],
        revision=row["revision"],
        deadline_revision=row["deadline_revision"],
        overdue=overdue,
        is_new=seen is None,
        is_updated=seen is not None and row["revision"] > seen,
        is_overdue=overdue and (row["seen_deadline_revision"] or 0) < row["deadline_revision"],
    )


class TaskAttentionService:
    def __init__(self, repository: TaskAttentionRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def snapshot(self, user_id: int) -> TaskAttentionSnapshot:
        """Возвращает число задач, а не число событий; категории могут пересекаться."""
        try:
            items = [
                attention_item(row, datetime.now(UTC).date())
                for row in await self.repository.get_rows(user_id=user_id)
            ]
            return TaskAttentionSnapshot(
                new_tasks=sum(item.is_new for item in items),
                overdue_tasks=sum(item.is_overdue for item in items),
                updated_tasks=sum(item.is_updated for item in items),
                total=sum(item.is_new or item.is_overdue or item.is_updated for item in items),
                items=items,
            )
        except TaskAttentionRepositoryError as error:
            raise TaskAttentionServiceError(str(error)) from error

    async def filter_ids(self, user_id: int, kind: str) -> set[int]:
        """Отбирает непросмотренные задачи до применения лимита списка в интерфейсе."""
        snapshot = await self.snapshot(user_id)
        return {
            item.task_id
            for item in snapshot.items
            if (
                item.is_new
                if kind == "new"
                else item.is_overdue
                if kind == "overdue"
                else item.is_updated
                if kind == "updated"
                else item.is_new or item.is_overdue or item.is_updated
            )
        }

    async def token(self, user_id: int, task_id: int) -> TaskAttentionItem:
        """Снимок версии перед загрузкой карточки, без побочного подтверждения просмотра."""
        try:
            rows = await self.repository.get_rows(user_id=user_id, task_id=task_id)
            if not rows:
                raise TaskNotFoundError(task_id=task_id)
            return attention_item(rows[0], datetime.now(UTC).date())
        except TaskAttentionRepositoryError as error:
            raise TaskAttentionServiceError(str(error)) from error

    async def mark_viewed(self, user_id: int, task_id: int, view: TaskViewSchema) -> None:
        """Подтверждает переданный снимок; более новые комментарии остаются непросмотренными."""
        current = await self.token(user_id, task_id)
        if (
            view.revision > current.revision
            or view.deadline_revision > current.deadline_revision
            or (
                view.overdue
                and view.deadline_revision == current.deadline_revision
                and not current.overdue
            )
        ):
            raise TaskAttentionVersionError("Версия просмотра больше текущей.")
        try:
            await self.repository.mark_viewed(
                user_id=user_id,
                task_id=task_id,
                revision=view.revision,
                deadline_revision=view.deadline_revision if view.overdue else 0,
            )
            await self.unit_of_work.commit()
        except (TaskAttentionRepositoryError, UnitOfWorkRepositoryError) as error:
            raise TaskAttentionServiceError(str(error)) from error
