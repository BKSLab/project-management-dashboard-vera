"""Инструменты задач, назначений, чек-листов и обсуждения."""

from src.agent.tools import AgentToolContext
from src.exceptions.agent_tools import AgentToolConflictError
from src.schemas import project_tool_inputs as inputs
from src.services.agent_action_helpers import checked_comment, checked_task, page
from src.services.agent_tool_scope import AgentProjectToolScope


async def list_tasks(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.TaskListInput
) -> dict:
    """Возвращает ограниченный список задач текущего проекта."""
    if args.stage_id is not None:
        await db.stages.get_stage_in_project(ctx.project_id, args.stage_id)
    rows = await db.tasks.get_task_list(ctx.project_id, stage_id=args.stage_id, search=args.search)
    result = page(rows, args)
    for item in result["items"]:
        item.pop("description_md", None)
        item.pop("checklist", None)
    return result


async def get_task(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.TaskInput
) -> dict:
    """Читает задачу с актуальными назначениями и ревизией чек-листа."""
    task = await checked_task(db, ctx, args.task_id)
    return {"task": task.model_dump(mode="json"), "source_id": f"task:{task.id}"}


async def create_task(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.TaskCreateInput
) -> dict:
    """Создаёт задачу через обычный сценарий нумерации и ролевых назначений."""
    task = await db.tasks.create_task(
        ctx.project_id, args.model_dump(exclude_unset=True), created_by_user_id=ctx.user_id
    )
    return {"task": task.model_dump(mode="json"), "source_id": f"task:{task.id}"}


async def update_task(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.TaskUpdateInput
) -> dict:
    """Меняет только переданные поля, сохраняя авторство действия."""
    await checked_task(db, ctx, args.task_id)
    task = await db.tasks.update_task(
        args.task_id, args.changes.model_dump(exclude_unset=True), updated_by_user_id=ctx.user_id
    )
    return {"task": task.model_dump(mode="json"), "source_id": f"task:{task.id}"}


async def move_task(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.TaskMoveInput
) -> dict:
    """Меняет стадию и положение задачи с обычной историей переходов."""
    await checked_task(db, ctx, args.task_id)
    task = await db.tasks.move_task(args.task_id, args.stage_id, args.position)
    return {"task": task.model_dump(mode="json"), "source_id": f"task:{task.id}"}


async def delete_task(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.TaskDeleteInput
) -> dict:
    """Удаляет только ту версию задачи, которую прочитал инициатор."""
    task = await checked_task(db, ctx, args.task_id)
    if task.updated_at != args.expected_updated_at:
        raise AgentToolConflictError("После подготовки удаления задача изменилась.")
    await db.tasks.delete_task(task.id, expected_updated_at=args.expected_updated_at)
    return {"deleted": True, "task_key": task.key, "title": task.title}


async def set_checklist(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.ChecklistInput
) -> dict:
    """Создаёт, изменяет или удаляет чек-лист по его текущей ревизии."""
    await checked_task(db, ctx, args.task_id)
    task = await db.tasks.update_task(
        args.task_id, args.model_dump(exclude={"task_id"}), updated_by_user_id=ctx.user_id
    )
    return {
        "task_key": task.key,
        "checklist": task.checklist.model_dump(mode="json") if task.checklist else None,
        "checklist_revision": task.checklist_revision,
        "source_id": f"task:{task.id}",
    }


async def fix_baseline(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.TaskInput
) -> dict:
    """Фиксирует текущие даты как baseline отдельной явной операцией."""
    await checked_task(db, ctx, args.task_id)
    return {
        "task": (await db.tasks.fix_baseline(args.task_id)).model_dump(mode="json"),
        "source_id": f"task:{args.task_id}",
    }


async def list_comments(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.TaskPageInput
) -> dict:
    """Возвращает комментарии доступной задачи."""
    await checked_task(db, ctx, args.task_id)
    return page(await db.comments.get_comments(args.task_id), args)


async def add_comment(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.CommentCreateInput
) -> dict:
    """Добавляет комментарий с подписью реального инициатора."""
    await checked_task(db, ctx, args.task_id)
    item = await db.comments.add_comment(args.task_id, ctx.display_name, args.body_md)
    return {"comment": item.model_dump(mode="json"), "source_id": f"comment:{item.id}"}


async def update_comment(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.CommentUpdateInput
) -> dict:
    """Редактирует прочитанную версию комментария без смены автора."""
    await checked_comment(db, ctx, args.comment_id)
    item = await db.comments.update_comment(args.comment_id, args.body_md, args.expected_body_md)
    return {"comment": item.model_dump(mode="json"), "source_id": f"comment:{item.id}"}


async def delete_comment(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.CommentInput
) -> dict:
    """Удаляет комментарий из проекта разговора."""
    await checked_comment(db, ctx, args.comment_id)
    await db.comments.delete_comment(args.comment_id)
    return {"deleted": True, "comment_id": args.comment_id}
