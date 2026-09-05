import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.access import require_link_access
from src.dependencies.auth import PrincipalDep, require_write_scope
from src.dependencies.services import DocumentLinksServiceDep
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.documents import DocumentsServiceError
from src.exceptions.tasks import TasksServiceError
from src.schemas.document_links import DocumentLinkCreateSchema, DocumentLinkSchema

router = APIRouter(prefix="/document-links", tags=["document-links"])
logger = logging.getLogger(__name__)

LinkErrors = (DocumentLinksServiceError, DocumentsServiceError, TasksServiceError)


@router.post(
    path="",
    dependencies=[Depends(require_write_scope)],
    status_code=status.HTTP_201_CREATED,
    summary="Связать документ с задачей",
    description="Создаёт связь документа и задачи одного проекта.",
    operation_id="createDocumentLink",
    response_description="Созданная связь.",
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
    principal: PrincipalDep,
    service: DocumentLinksServiceDep,
) -> DocumentLinkSchema:
    """Создаёт связь документа с задачей.

    Args:
        data: Идентификаторы документа и задачи.
        principal: Принципал текущего запроса.
        service: Сервис связей документов.

    Returns:
        Созданная связь.

    Raises:
        HTTPException: Если объекты не найдены, принадлежат разным проектам
            или создать связь не удалось.
    """
    logger.info(
        "🚀 Запрос POST /document-links. Документ: %s, задача: %s.",
        data.document_id,
        data.task_id,
    )
    try:
        result = await service.create_link(
            document_id=data.document_id,
            task_id=data.task_id,
            user_id=principal.user_id,
        )
        logger.info("✅ Связь документа создана. id=%s.", result.id)
        return result
    except LinkErrors as error:
        logger.exception("❌ Ошибка POST /document-links. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/{link_id}",
    dependencies=[Depends(require_write_scope), Depends(require_link_access)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить связь документа",
    description="Удаляет связь документа с задачей. Сами объекты не удаляются.",
    operation_id="deleteDocumentLink",
    response_description="Связь удалена.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_document_link(
    link_id: Annotated[int, Path(gt=0, description="Идентификатор связи.")],
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
    except LinkErrors as error:
        logger.exception("❌ Ошибка DELETE /document-links/%s. Детали: %s", link_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
