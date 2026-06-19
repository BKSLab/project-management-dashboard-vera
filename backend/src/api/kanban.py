import logging
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.dependencies.services import DocumentLinksServiceDep, KanbanServiceDep
from src.exceptions.repositories import DocumentLinksRepositoryError, KanbanRepositoryError
from src.exceptions.services import (
    KanbanStageHasTasksError,
    KanbanStageNotFoundError,
    KanbanTaskFromWbsDeleteError,
    KanbanTaskNotFoundError,
    TaskCommentNotFoundError,
)
from src.schemas.document_links import LinkedDocumentSchema
from src.schemas.kanban import (
    ActivitySchema,
    CommentCreateSchema,
    CommentSchema,
    StageCreateSchema,
    StageSchema,
    StageUpdateSchema,
    TaskCreateSchema,
    TaskMoveSchema,
    TaskSchema,
    TaskUpdateSchema,
)

router = APIRouter()
logger = logging.getLogger(__name__)

ServiceErrors = (
    KanbanRepositoryError,
    KanbanStageNotFoundError,
    KanbanStageHasTasksError,
    KanbanTaskNotFoundError,
    KanbanTaskFromWbsDeleteError,
    TaskCommentNotFoundError,
)


@router.get("/stages", status_code=status.HTTP_200_OK, response_model=list[StageSchema])
async def get_stages(kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.get_stage_list()
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при получении стадий. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.post("/stages", status_code=status.HTTP_201_CREATED, response_model=StageSchema)
async def create_stage(data: StageCreateSchema, kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.create_stage(data=data.model_dump())
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при создании стадии. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.patch("/stages/{stage_id}", status_code=status.HTTP_200_OK, response_model=StageSchema)
async def update_stage(stage_id: int, data: StageUpdateSchema, kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.update_stage(
            stage_id=stage_id, data=data.model_dump(exclude_unset=True)
        )
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при обновлении стадии id=%s. %s", stage_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stage(stage_id: int, kanban_service: KanbanServiceDep):
    try:
        await kanban_service.delete_stage(stage_id=stage_id)
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при удалении стадии id=%s. %s", stage_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.get("/tasks", status_code=status.HTTP_200_OK, response_model=list[TaskSchema])
async def get_tasks(
    kanban_service: KanbanServiceDep,
    stage_id: Annotated[Optional[int], Query()] = None,
):
    try:
        return await kanban_service.get_task_list(stage_id=stage_id)
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при получении задач. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskSchema)
async def create_task(data: TaskCreateSchema, kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.create_task(data=data.model_dump())
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при создании задачи. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.patch("/tasks/{task_id}", status_code=status.HTTP_200_OK, response_model=TaskSchema)
async def update_task(task_id: int, data: TaskUpdateSchema, kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.update_task(
            task_id=task_id, data=data.model_dump(exclude_unset=True)
        )
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при обновлении задачи id=%s. %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.patch("/tasks/{task_id}/move", status_code=status.HTTP_200_OK, response_model=TaskSchema)
async def move_task(task_id: int, data: TaskMoveSchema, kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.move_task(
            task_id=task_id, stage_id=data.stage_id, position=data.position
        )
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при перемещении задачи id=%s. %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, kanban_service: KanbanServiceDep):
    try:
        await kanban_service.delete_task(task_id=task_id)
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при удалении задачи id=%s. %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.get(
    "/tasks/{task_id}/comments", status_code=status.HTTP_200_OK, response_model=list[CommentSchema]
)
async def get_comments(task_id: int, kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.get_comments(task_id=task_id)
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при получении комментариев задачи id=%s. %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.post(
    "/tasks/{task_id}/comments", status_code=status.HTTP_201_CREATED, response_model=CommentSchema
)
async def add_comment(task_id: int, data: CommentCreateSchema, kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.add_comment(
            task_id=task_id, author_name=data.author_name, body_md=data.body_md
        )
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при добавлении комментария к задаче id=%s. %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: int, kanban_service: KanbanServiceDep):
    try:
        await kanban_service.delete_comment(comment_id=comment_id)
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при удалении комментария id=%s. %s", comment_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.get(
    "/tasks/{task_id}/activity", status_code=status.HTTP_200_OK, response_model=list[ActivitySchema]
)
async def get_activity(task_id: int, kanban_service: KanbanServiceDep):
    try:
        return await kanban_service.get_activity(task_id=task_id)
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при получении истории задачи id=%s. %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.get(
    "/tasks/{task_id}/links", status_code=status.HTTP_200_OK, response_model=list[LinkedDocumentSchema]
)
async def get_task_links(
    task_id: int,
    kanban_service: KanbanServiceDep,
    document_links_service: DocumentLinksServiceDep,
):
    try:
        await kanban_service.get_task(task_id=task_id)
        return await document_links_service.get_links_for_task(kanban_task_id=task_id)
    except (*ServiceErrors, DocumentLinksRepositoryError) as error:
        logger.exception("❌ Ошибка при получении связанных документов задачи id=%s. %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)
