import logging

from fastapi import APIRouter, HTTPException, status

from src.dependencies.services import DocumentLinksServiceDep
from src.exceptions.repositories import DocumentLinksRepositoryError
from src.exceptions.services import DocumentLinkInvalidError, DocumentLinkNotFoundError
from src.schemas.document_links import DocumentLinkCreateSchema, DocumentLinkSchema

router = APIRouter()
logger = logging.getLogger(__name__)

ServiceErrors = (DocumentLinksRepositoryError, DocumentLinkInvalidError, DocumentLinkNotFoundError)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentLinkSchema)
async def create_document_link(
    data: DocumentLinkCreateSchema,
    document_links_service: DocumentLinksServiceDep,
):
    try:
        return await document_links_service.create_link(
            document_id=data.document_id,
            kanban_task_id=data.kanban_task_id,
            wbs_item_id=data.wbs_item_id,
        )
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при создании связи документа. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_link(link_id: int, document_links_service: DocumentLinksServiceDep):
    try:
        await document_links_service.delete_link(link_id=link_id)
    except ServiceErrors as error:
        logger.exception("❌ Ошибка при удалении связи документа id=%s. %s", link_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)
