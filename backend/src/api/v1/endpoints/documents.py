import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.access import require_document_access, require_project_access
from src.dependencies.auth import require_write_scope
from src.dependencies.services import DocumentLinksServiceDep, DocumentsServiceDep
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.documents import DocumentsServiceError
from src.exceptions.projects import ProjectsServiceError
from src.schemas.document_links import LinkedTaskSchema
from src.schemas.documents import (
    DocumentCreateSchema,
    DocumentDetailSchema,
    DocumentSchema,
    DocumentUpdateSchema,
)

router = APIRouter(tags=["documents"])
logger = logging.getLogger(__name__)

DocumentErrors = (DocumentsServiceError, ProjectsServiceError)


@router.get(
    path="/projects/{project_id}/documents",
    dependencies=[Depends(require_project_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить документы проекта",
    description="Возвращает документы проекта с опциональным полнотекстовым поиском.",
    operation_id="getProjectDocuments",
    response_description="Список документов проекта.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[DocumentSchema],
)
async def get_documents(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    service: DocumentsServiceDep,
    search: Annotated[
        str | None,
        Query(max_length=200, description="Поиск по заголовку, содержимому или slug."),
    ] = None,
) -> list[DocumentSchema]:
    """Получает документы проекта.

    Args:
        project_id: Идентификатор проекта.
        service: Сервис документов.
        search: Опциональная поисковая строка.

    Returns:
        Список документов.

    Raises:
        HTTPException: Если проект не найден или получить документы не удалось.
    """
    logger.info("🚀 Запрос GET /projects/%s/documents. search=%s.", project_id, search)
    try:
        result = await service.get_document_list(project_id=project_id, search=search)
        logger.info("✅ Документы проекта id=%s получены. Найдено: %s.", project_id, len(result))
        return result
    except DocumentErrors as error:
        logger.exception("❌ Ошибка GET /projects/%s/documents. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/projects/{project_id}/documents",
    dependencies=[Depends(require_write_scope), Depends(require_project_access)],
    status_code=status.HTTP_201_CREATED,
    summary="Создать документ проекта",
    description="Создаёт документ, подбирая свободный slug внутри проекта.",
    operation_id="createProjectDocument",
    response_description="Созданный документ.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=DocumentDetailSchema,
)
async def create_document(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    data: DocumentCreateSchema,
    service: DocumentsServiceDep,
) -> DocumentDetailSchema:
    """Создаёт документ проекта.

    Args:
        project_id: Идентификатор проекта.
        data: Поля нового документа.
        service: Сервис документов.

    Returns:
        Созданный документ.

    Raises:
        HTTPException: Если проект не найден или создать документ не удалось.
    """
    logger.info("🚀 Запрос POST /projects/%s/documents. Заголовок: %s.", project_id, data.title)
    try:
        result = await service.create_document(
            project_id=project_id,
            title=data.title,
            slug=data.slug,
            content_md=data.content_md,
        )
        logger.info("✅ Документ создан. id=%s, slug=%s.", result.id, result.slug)
        return result
    except DocumentErrors as error:
        logger.exception("❌ Ошибка POST /projects/%s/documents. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/documents/{document_id}",
    dependencies=[Depends(require_document_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить документ",
    description="Возвращает документ с Markdown-содержимым.",
    operation_id="getDocument",
    response_description="Документ проекта.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=DocumentDetailSchema,
)
async def get_document(
    document_id: Annotated[int, Path(gt=0, description="Идентификатор документа.")],
    service: DocumentsServiceDep,
) -> DocumentDetailSchema:
    """Получает документ по идентификатору.

    Args:
        document_id: Идентификатор документа.
        service: Сервис документов.

    Returns:
        Документ с содержимым.

    Raises:
        HTTPException: Если документ не найден или получить его не удалось.
    """
    logger.info("🚀 Запрос GET /documents/%s.", document_id)
    try:
        result = await service.get_document(document_id=document_id)
        logger.info("✅ Документ id=%s получен.", document_id)
        return result
    except DocumentErrors as error:
        logger.exception("❌ Ошибка GET /documents/%s. Детали: %s", document_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/documents/{document_id}",
    dependencies=[Depends(require_write_scope), Depends(require_document_access)],
    status_code=status.HTTP_200_OK,
    summary="Изменить документ",
    description="Частично обновляет заголовок и содержимое документа.",
    operation_id="updateDocument",
    response_description="Обновлённый документ.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=DocumentDetailSchema,
)
async def update_document(
    document_id: Annotated[int, Path(gt=0, description="Идентификатор документа.")],
    data: DocumentUpdateSchema,
    service: DocumentsServiceDep,
) -> DocumentDetailSchema:
    """Обновляет документ.

    Args:
        document_id: Идентификатор документа.
        data: Изменяемые поля документа.
        service: Сервис документов.

    Returns:
        Обновлённый документ.

    Raises:
        HTTPException: Если документ не найден или обновить его не удалось.
    """
    logger.info("🚀 Запрос PATCH /documents/%s.", document_id)
    try:
        result = await service.update_document(
            document_id=document_id,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Документ id=%s обновлён.", document_id)
        return result
    except DocumentErrors as error:
        logger.exception("❌ Ошибка PATCH /documents/%s. Детали: %s", document_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/documents/{document_id}",
    dependencies=[Depends(require_write_scope), Depends(require_document_access)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить документ",
    description="Удаляет документ и его связи с задачами.",
    operation_id="deleteDocument",
    response_description="Документ удалён.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_document(
    document_id: Annotated[int, Path(gt=0, description="Идентификатор документа.")],
    service: DocumentsServiceDep,
) -> None:
    """Удаляет документ.

    Args:
        document_id: Идентификатор документа.
        service: Сервис документов.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если документ не найден или удалить его не удалось.
    """
    logger.info("🚀 Запрос DELETE /documents/%s.", document_id)
    try:
        await service.delete_document(document_id=document_id)
        logger.info("✅ Документ id=%s удалён.", document_id)
    except DocumentErrors as error:
        logger.exception("❌ Ошибка DELETE /documents/%s. Детали: %s", document_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/documents/{document_id}/links",
    dependencies=[Depends(require_document_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить задачи документа",
    description="Возвращает задачи, связанные с документом.",
    operation_id="getDocumentLinks",
    response_description="Связанные задачи.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[LinkedTaskSchema],
)
async def get_document_links(
    document_id: Annotated[int, Path(gt=0, description="Идентификатор документа.")],
    service: DocumentLinksServiceDep,
) -> list[LinkedTaskSchema]:
    """Получает связанные с документом задачи.

    Args:
        document_id: Идентификатор документа.
        service: Сервис связей документов.

    Returns:
        Список связанных задач.

    Raises:
        HTTPException: Если документ не найден или получить связи не удалось.
    """
    logger.info("🚀 Запрос GET /documents/%s/links.", document_id)
    try:
        result = await service.get_links_for_document(document_id=document_id)
        logger.info("✅ Связи документа id=%s получены. Найдено: %s.", document_id, len(result))
        return result
    except (DocumentLinksServiceError, DocumentsServiceError) as error:
        logger.exception("❌ Ошибка GET /documents/%s/links. Детали: %s", document_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
