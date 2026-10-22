"""Board actions share the current user's access, scene and atomic batch service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from src.agent.tools import AgentToolContext
from src.exceptions.agent_tools import (
    AgentToolAccessError,
    AgentToolArgumentsError,
    AgentToolConflictError,
    AgentToolOperationError,
)
from src.schemas.board_diagrams import (
    BoardArrangeInput,
    BoardDiagramInput,
    BoardSceneInput,
    BoardShapeUpdatesInput,
    PersonalBoardsInput,
)
from src.schemas.board_shapes import BoardBatchSchema
from src.services.board_arrange import compile_arrangement
from src.services.board_layout import DiagramLayoutError, compile_diagram

if TYPE_CHECKING:
    from src.services.agent_tool_scope import AgentProjectToolScope


async def _scene(
    db: AgentProjectToolScope,
    ctx: AgentToolContext,
    board_id: int,
    *,
    write: bool = False,
):
    if ctx.user_id is None:
        raise AgentToolAccessError("Нужен аутентифицированный пользователь.")
    if write and not ctx.can_write:
        raise AgentToolAccessError("Текущий запрос не разрешает запись.")
    if ctx.project_id is not None:
        grant = await db.access.ensure_project_access(
            project_id=ctx.project_id, user_id=ctx.user_id
        )
        if write and not grant.can_write:
            raise AgentToolAccessError("Доска проекта доступна только для чтения.")
    service = getattr(db, "board_shapes", None)
    if service is not None and getattr(service, "editor_repository", None) is not None:
        # ACL first, then board lock before reading objects/metadata. All shared
        # mutations hold this lock too, so the returned scene is one snapshot.
        await service._require_board(ctx.project_id, board_id, user_id=ctx.user_id)
    if ctx.project_id is None:
        return await db.boards.get_free_content(board_id=board_id, user_id=ctx.user_id)
    return await db.boards.get_content(project_id=ctx.project_id, board_id=board_id)


async def _editor_metadata(db, board_id: int) -> dict:
    service = getattr(db, "board_shapes", None)
    repository = getattr(service, "editor_repository", None)
    if repository is None:
        return {"groups": [], "locked": []}
    board = await repository.get_board(board_id, lock=True)
    raw = board.editor_metadata or {}
    # Templates include copied object contents and are not model context.
    return {"groups": raw.get("groups", []), "locked": raw.get("locked", [])}


def _objects(scene) -> list[dict[str, Any]]:
    return [{**shape.model_dump(mode="json"), "type": "shape"} for shape in scene.shapes] + [
        {
            **sticker.model_dump(mode="json"),
            "type": "sticker",
            "x": sticker.canvas_x,
            "y": sticker.canvas_y,
            "w": sticker.width,
            "h": sticker.height,
        }
        for sticker in scene.stickers
    ]


async def list_personal_boards(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: PersonalBoardsInput
) -> dict:
    if ctx.user_id is None:
        raise AgentToolAccessError("Нужен аутентифицированный пользователь.")
    items = await db.boards.list_free_boards(user_id=ctx.user_id)
    end = args.offset + args.limit
    return {
        "items": [item.model_dump(mode="json") for item in items[args.offset : end]],
        "total": len(items),
        "next_offset": end if end < len(items) else None,
    }


async def get_board_scene(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: BoardSceneInput
) -> dict:
    scene = await _scene(db, ctx, args.board_id)
    objects = sorted(_objects(scene), key=lambda item: (item["type"], item["id"]))
    end = args.offset + args.limit
    return {
        "board": scene.board.model_dump(mode="json"),
        "revision": scene.board.revision,
        "editor_metadata": await _editor_metadata(db, args.board_id),
        "objects": objects[args.offset : end],
        "total": len(objects),
        "next_offset": end if end < len(objects) else None,
    }


async def _apply(
    db: AgentProjectToolScope,
    ctx: AgentToolContext,
    board_id: int,
    batch: BoardBatchSchema,
    *,
    before: list[dict[str, Any]],
) -> dict:
    if db.board_shapes is None:
        raise AgentToolOperationError("Сервис рисования доски не настроен.")
    result = await db.board_shapes.apply_batch(
        project_id=ctx.project_id,
        board_id=board_id,
        data=batch,
        author_id=ctx.user_id,
    )
    # The frontend can refresh only this board and register this complete delta as
    # one history entry. No follow-up individual shape writes are required.
    return {
        "board_change": {
            "board_id": board_id,
            "project_id": ctx.project_id,
            "operation_count": len(batch.ops),
            "before_shapes": before,
            "batch": result.model_dump(mode="json"),
        },
    }


async def draw_board_diagram(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: BoardDiagramInput
) -> dict:
    scene = await _scene(db, ctx, args.board_id, write=True)
    try:
        batch = compile_diagram(args, occupied=_objects(scene))
    except (DiagramLayoutError, ValidationError) as error:
        raise AgentToolArgumentsError(
            "Схема не помещается на доске или содержит недоступные привязки."
        ) from error
    return await _apply(db, ctx, args.board_id, batch, before=[])


async def arrange_board_objects(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: BoardArrangeInput
) -> dict:
    scene = await _scene(db, ctx, args.board_id, write=True)
    if scene.board.revision != args.expected_revision:
        raise AgentToolConflictError(
            "Доска изменилась; перечитайте сцену и сохраните чужие правки."
        )
    objects = _objects(scene)
    current = {(item["type"], item["id"]): item for item in objects}
    for ref in args.objects:
        item = current.get((ref.type, ref.id))
        if item is None:
            raise AgentToolAccessError("Объект недоступен на этой доске.")
        if item["revision"] != ref.revision:
            raise AgentToolConflictError("Объект изменился; перечитайте свежую сцену.")
    try:
        batch = compile_arrangement(
            args, objects=objects, metadata=await _editor_metadata(db, args.board_id)
        )
    except (DiagramLayoutError, ValidationError) as error:
        raise AgentToolArgumentsError(str(error)) from error
    changed_shapes = {op.id for op in batch.ops if op.op == "update_shape"}
    result = await _apply(
        db,
        ctx,
        args.board_id,
        batch,
        before=[
            item for item in objects if item["type"] == "shape" and item["id"] in changed_shapes
        ],
    )
    result["board_change"]["before_stickers"] = [
        item
        for item in objects
        if item["type"] == "sticker"
        and ("sticker", item["id"]) in {(ref.type, ref.id) for ref in args.objects}
    ]
    return result


async def update_board_shapes(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: BoardShapeUpdatesInput
) -> dict:
    scene = await _scene(db, ctx, args.board_id, write=True)
    current = {item.id: item for item in scene.shapes}
    before = []
    for item in args.updates:
        shape = current.get(item.id)
        if shape is None:
            raise AgentToolAccessError("Фигура недоступна на этой доске.")
        if shape.revision != item.revision:
            raise AgentToolConflictError("Фигура изменилась; прочитайте свежую сцену.")
        before.append(shape.model_dump(mode="json"))
    batch = BoardBatchSchema.model_validate(
        {
            "ops": [
                {
                    "op": "update_shape",
                    "id": item.id,
                    "revision": item.revision,
                    "data": item.data.model_dump(mode="json", exclude_unset=True),
                }
                for item in args.updates
            ]
        }
    )
    # apply_batch rechecks all revisions while holding row locks. The scene check
    # above never replaces the final concurrency check or the batch transaction.
    return await _apply(db, ctx, args.board_id, batch, before=before)
