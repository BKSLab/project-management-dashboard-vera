import logging

from src.db.models.kanban import TaskActivityEventType
from src.exceptions.services import (
    KanbanStageHasTasksError,
    KanbanStageNotFoundError,
    KanbanTaskFromWbsDeleteError,
    KanbanTaskNotFoundError,
    TaskCommentNotFoundError,
)
from src.repositories.kanban import KanbanRepository
from src.repositories.wbs import WbsRepository
from src.schemas.kanban import (
    ActivitySchema,
    CommentSchema,
    StageSchema,
    TaskSchema,
)

logger = logging.getLogger(__name__)


class KanbanService:
    """Сервис бизнес-логики канбан-доски."""

    def __init__(self, kanban_repository: KanbanRepository, wbs_repository: WbsRepository):
        self.kanban_repository = kanban_repository
        self.wbs_repository = wbs_repository

    async def _build_wbs_context(self) -> dict[int, tuple[str, str | None]]:
        """Строит карту wbs_item_id -> (код, название фазы верхнего уровня предка)."""
        items = await self.wbs_repository.get_all_items()
        by_id = {item.id: item for item in items}

        def phase_name_of(item) -> str | None:
            node = item
            while node.parent_id is not None:
                node = by_id.get(node.parent_id)
                if node is None:
                    return None
            return node.phase_name

        return {item.id: (item.code, phase_name_of(item)) for item in items}

    async def _build_comment_context(self) -> dict[int, tuple[int, str]]:
        """Строит карту task_id -> (кол-во комментариев, текст последнего по created_at)."""
        comments = await self.kanban_repository.get_all_comments()
        context: dict[int, tuple[int, str]] = {}
        for comment in comments:
            count, _ = context.get(comment.task_id, (0, ""))
            context[comment.task_id] = (count + 1, comment.body_md)
        return context

    # --- Стадии ---

    async def get_stage_list(self) -> list[StageSchema]:
        stages = await self.kanban_repository.get_all_stages()
        return [StageSchema.model_validate(stage) for stage in stages]

    async def create_stage(self, data: dict) -> StageSchema:
        stage = await self.kanban_repository.create_stage(data=data)
        return StageSchema.model_validate(stage)

    async def update_stage(self, stage_id: int, data: dict) -> StageSchema:
        stage = await self.kanban_repository.get_stage_by_id(stage_id=stage_id)
        if stage is None:
            raise KanbanStageNotFoundError(stage_id=stage_id)
        updated = await self.kanban_repository.update_stage(stage=stage, data=data)
        return StageSchema.model_validate(updated)

    async def delete_stage(self, stage_id: int) -> None:
        stage = await self.kanban_repository.get_stage_by_id(stage_id=stage_id)
        if stage is None:
            raise KanbanStageNotFoundError(stage_id=stage_id)

        tasks_count = await self.kanban_repository.count_tasks_in_stage(stage_id=stage_id)
        if tasks_count > 0:
            raise KanbanStageHasTasksError(stage_id=stage_id)

        await self.kanban_repository.delete_stage(stage=stage)

    # --- Задачи ---

    async def get_task_list(self, stage_id: int | None = None) -> list[TaskSchema]:
        tasks = await self.kanban_repository.get_tasks(stage_id=stage_id)
        wbs_context = await self._build_wbs_context()
        comment_context = await self._build_comment_context()

        result = []
        for task in tasks:
            schema = TaskSchema.model_validate(task)
            if task.wbs_item_id is not None and task.wbs_item_id in wbs_context:
                code, phase_name = wbs_context[task.wbs_item_id]
                schema.wbs_code = code
                schema.wbs_phase_name = phase_name
            schema.comments_count, schema.last_comment = comment_context.get(task.id, (0, None))
            result.append(schema)
        return result

    async def get_task(self, task_id: int) -> TaskSchema:
        task = await self.kanban_repository.get_task_by_id(task_id=task_id)
        if task is None:
            raise KanbanTaskNotFoundError(task_id=task_id)
        return TaskSchema.model_validate(task)

    async def create_task(self, data: dict) -> TaskSchema:
        stage_id = data.get("stage_id")
        if stage_id is None:
            stages = await self.kanban_repository.get_all_stages()
            if not stages:
                raise KanbanStageNotFoundError(stage_id=0)
            data["stage_id"] = stages[0].id
        else:
            stage = await self.kanban_repository.get_stage_by_id(stage_id=stage_id)
            if stage is None:
                raise KanbanStageNotFoundError(stage_id=stage_id)

        task = await self.kanban_repository.create_task(data=data)
        return TaskSchema.model_validate(task)

    async def update_task(self, task_id: int, data: dict) -> TaskSchema:
        task = await self.kanban_repository.get_task_by_id(task_id=task_id)
        if task is None:
            raise KanbanTaskNotFoundError(task_id=task_id)

        if "due_date" in data and data["due_date"] != task.due_date:
            await self.kanban_repository.create_activity(
                task_id=task_id,
                event_type=TaskActivityEventType.DUE_DATE_CHANGED,
                from_value=str(task.due_date) if task.due_date else None,
                to_value=str(data["due_date"]) if data["due_date"] else None,
            )
        if "description_md" in data and data["description_md"] != task.description_md:
            await self.kanban_repository.create_activity(
                task_id=task_id,
                event_type=TaskActivityEventType.DESCRIPTION_CHANGED,
                from_value=None,
                to_value=None,
            )

        updated = await self.kanban_repository.update_task(task=task, data=data)
        return TaskSchema.model_validate(updated)

    async def move_task(self, task_id: int, stage_id: int, position: float) -> TaskSchema:
        task = await self.kanban_repository.get_task_by_id(task_id=task_id)
        if task is None:
            raise KanbanTaskNotFoundError(task_id=task_id)

        target_stage = await self.kanban_repository.get_stage_by_id(stage_id=stage_id)
        if target_stage is None:
            raise KanbanStageNotFoundError(stage_id=stage_id)

        if task.stage_id != stage_id:
            current_stage = await self.kanban_repository.get_stage_by_id(stage_id=task.stage_id)
            await self.kanban_repository.create_activity(
                task_id=task_id,
                event_type=TaskActivityEventType.STAGE_CHANGED,
                from_value=current_stage.name if current_stage else None,
                to_value=target_stage.name,
            )

        updated = await self.kanban_repository.update_task(
            task=task, data={"stage_id": stage_id, "position": position}
        )
        return TaskSchema.model_validate(updated)

    async def delete_task(self, task_id: int) -> None:
        task = await self.kanban_repository.get_task_by_id(task_id=task_id)
        if task is None:
            raise KanbanTaskNotFoundError(task_id=task_id)
        if task.wbs_item_id is not None:
            raise KanbanTaskFromWbsDeleteError(task_id=task_id)
        await self.kanban_repository.delete_task(task=task)

    # --- Комментарии ---

    async def get_comments(self, task_id: int) -> list[CommentSchema]:
        task = await self.kanban_repository.get_task_by_id(task_id=task_id)
        if task is None:
            raise KanbanTaskNotFoundError(task_id=task_id)
        comments = await self.kanban_repository.get_comments(task_id=task_id)
        return [CommentSchema.model_validate(comment) for comment in comments]

    async def add_comment(self, task_id: int, author_name: str | None, body_md: str) -> CommentSchema:
        task = await self.kanban_repository.get_task_by_id(task_id=task_id)
        if task is None:
            raise KanbanTaskNotFoundError(task_id=task_id)

        comment = await self.kanban_repository.create_comment(
            task_id=task_id, author_name=author_name, body_md=body_md
        )
        await self.kanban_repository.create_activity(
            task_id=task_id,
            event_type=TaskActivityEventType.COMMENT_ADDED,
            from_value=None,
            to_value=body_md[:255],
        )
        return CommentSchema.model_validate(comment)

    async def delete_comment(self, comment_id: int) -> None:
        comment = await self.kanban_repository.get_comment_by_id(comment_id=comment_id)
        if comment is None:
            raise TaskCommentNotFoundError(comment_id=comment_id)
        await self.kanban_repository.delete_comment(comment=comment)

    # --- История ---

    async def get_activity(self, task_id: int) -> list[ActivitySchema]:
        task = await self.kanban_repository.get_task_by_id(task_id=task_id)
        if task is None:
            raise KanbanTaskNotFoundError(task_id=task_id)
        activity = await self.kanban_repository.get_activity(task_id=task_id)
        return [ActivitySchema.model_validate(item) for item in activity]
