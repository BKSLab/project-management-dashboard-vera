import logging

from fastapi import APIRouter, HTTPException, status

from src.dependencies.services import WbsServiceDep
from src.exceptions.repositories import KanbanRepositoryError, WbsRepositoryError
from src.exceptions.services import WbsItemNotFoundError
from src.schemas.wbs import (
    WbsItemCreateSchema,
    WbsItemSchema,
    WbsItemUpdateSchema,
    WbsNodeSchema,
)

router = APIRouter()
logger = logging.getLogger(__name__)

ServiceErrors = (WbsRepositoryError, KanbanRepositoryError, WbsItemNotFoundError)


@router.get("/tree", status_code=status.HTTP_200_OK, response_model=list[WbsNodeSchema])
async def get_tree(wbs_service: WbsServiceDep):
    try:
        return await wbs_service.get_tree()
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при получении дерева ИСР. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.post("/items", status_code=status.HTTP_201_CREATED, response_model=WbsItemSchema)
async def create_item(data: WbsItemCreateSchema, wbs_service: WbsServiceDep):
    try:
        return await wbs_service.create_item(
            parent_id=data.parent_id,
            title=data.title,
            role=data.role,
            phase_name=data.phase_name,
        )
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при создании узла ИСР. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.patch("/items/{item_id}", status_code=status.HTTP_200_OK, response_model=WbsItemSchema)
async def update_item(item_id: int, data: WbsItemUpdateSchema, wbs_service: WbsServiceDep):
    try:
        return await wbs_service.update_item(
            item_id=item_id, data=data.model_dump(exclude_unset=True)
        )
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при обновлении узла ИСР id=%s. %s", item_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, wbs_service: WbsServiceDep):
    try:
        await wbs_service.delete_item(item_id=item_id)
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при удалении узла ИСР id=%s. %s", item_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)
