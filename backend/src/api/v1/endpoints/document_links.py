import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.services import DocumentLinksServiceDep
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.documents import DocumentsServiceError
from src.exceptions.kanban_tasks import KanbanTasksServiceError
from src.exceptions.wbs import WbsServiceError
from src.schemas.document_links import DocumentLinkCreateSchema, DocumentLinkSchema

router = APIRouter(prefix="/document-links", tags=["document-links"])
logger = logging.getLogger(__name__)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать связь документа",
    description="Связывает документ ровно с одной задачей канбана или узлом ИСР.",
    operation_id="createDocumentLink",
    response_description="Созданная связь документа.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=DocumentLinkSchema,
)
async def create_document_link(
    data: DocumentLinkCreateSchema,
    service: DocumentLinksServiceDep,
) -> DocumentLinkSchema:
    """Создаёт связь документа с целевым объектом.

    Args:
        data: Документ и ровно один целевой объект.
        service: Сервис связей документов.

    Returns:
        Созданная связь.

    Raises:
        HTTPException: Если объект не найден, связь невалидна или сохранить её не удалось.
    """
    logger.info(
        "🚀 Запрос POST /document-links. document_id=%s, task_id=%s, wbs_id=%s.",
        data.document_id,
        data.kanban_task_id,
        data.wbs_item_id,
    )
    try:
        result = await service.create_link(
            document_id=data.document_id,
            kanban_task_id=data.kanban_task_id,
            wbs_item_id=data.wbs_item_id,
        )
        logger.info("✅ Связь документа создана. id=%s.", result.id)
        return result
    except (
        DocumentLinksServiceError,
        DocumentsServiceError,
        KanbanTasksServiceError,
        WbsServiceError,
    ) as error:
        logger.exception("❌ Ошибка POST /document-links. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить связь документа",
    description="Удаляет связь документа, не удаляя сам документ или целевой объект.",
    operation_id="deleteDocumentLink",
    response_description="Связь документа удалена.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_document_link(
    link_id: Annotated[int, Path(gt=0, description="Идентификатор связи документа.")],
    service: DocumentLinksServiceDep,
) -> None:
    """Удаляет связь документа.

    Args:
        link_id: Идентификатор связи.
        service: Сервис связей документов.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если связь не найдена или удалить её не удалось.
    """
    logger.info("🚀 Запрос DELETE /document-links/%s.", link_id)
    try:
        await service.delete_link(link_id=link_id)
        logger.info("✅ Связь документа id=%s удалена.", link_id)
    except DocumentLinksServiceError as error:
        logger.exception("❌ Ошибка DELETE /document-links/%s. Детали: %s", link_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
