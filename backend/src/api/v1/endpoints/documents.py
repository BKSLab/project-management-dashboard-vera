import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.services import DocumentLinksServiceDep, DocumentsServiceDep
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.documents import DocumentNotFoundError, DocumentsServiceError
from src.schemas.document_links import LinkedTargetSchema
from src.schemas.documents import (
    DocumentCreateSchema,
    DocumentDetailSchema,
    DocumentSchema,
    DocumentUpdateSchema,
)

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)


@router.get(
    path="",
    status_code=status.HTTP_200_OK,
    summary="Получить документы",
    description="Возвращает документы, при необходимости отфильтрованные полнотекстовым поиском.",
    operation_id="getDocuments",
    response_description="Список документов с фрагментами поисковых совпадений.",
    responses={422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[DocumentSchema],
)
async def get_documents(
    documents_service: DocumentsServiceDep,
    search: Annotated[
        str | None,
        Query(max_length=200, description="Поиск по заголовку, содержимому или slug."),
    ] = None,
) -> list[DocumentSchema]:
    """Получает список документов.

    Args:
        documents_service: Сервис документов.
        search: Опциональная строка поиска.

    Returns:
        Список найденных документов.

    Raises:
        HTTPException: Если сервис не смог получить документы.
    """
    logger.info("🚀 Запрос GET /documents. Поиск: %s.", search)
    try:
        result = await documents_service.get_document_list(search=search)
        logger.info("✅ Запрос GET /documents выполнен. Найдено: %s.", len(result))
        return result
    except DocumentsServiceError as error:
        logger.exception("❌ Ошибка GET /documents. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать документ",
    description="Создаёт редактируемый Markdown-документ с уникальным slug.",
    operation_id="createDocument",
    response_description="Созданный документ.",
    responses={409: CONFLICT_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=DocumentDetailSchema,
)
async def create_document(
    data: DocumentCreateSchema,
    documents_service: DocumentsServiceDep,
) -> DocumentDetailSchema:
    """Создаёт документ.

    Args:
        data: Поля нового документа.
        documents_service: Сервис документов.

    Returns:
        Созданный документ.

    Raises:
        HTTPException: Если документ создать не удалось.
    """
    logger.info("🚀 Запрос POST /documents. Заголовок: %s.", data.title)
    try:
        result = await documents_service.create_document(
            title=data.title,
            slug=data.slug,
            content_md=data.content_md,
        )
        logger.info("✅ Документ создан. slug=%s.", result.slug)
        return result
    except DocumentsServiceError as error:
        logger.exception("❌ Ошибка POST /documents. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/{slug}",
    status_code=status.HTTP_200_OK,
    summary="Получить документ",
    description="Возвращает полное содержимое документа по его URL-идентификатору.",
    operation_id="getDocument",
    response_description="Документ с Markdown-содержимым.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=DocumentDetailSchema,
)
async def get_document(
    slug: Annotated[str, Path(description="URL-идентификатор документа.")],
    documents_service: DocumentsServiceDep,
) -> DocumentDetailSchema:
    """Получает документ по slug.

    Args:
        slug: URL-идентификатор документа.
        documents_service: Сервис документов.

    Returns:
        Полный документ.

    Raises:
        HTTPException: Если документ не найден или получить его не удалось.
    """
    logger.info("🚀 Запрос GET /documents/%s.", slug)
    try:
        result = await documents_service.get_document_by_slug(slug=slug)
        logger.info("✅ Документ slug=%s получен.", slug)
        return result
    except (DocumentNotFoundError, DocumentsServiceError) as error:
        logger.exception("❌ Ошибка GET /documents/%s. Детали: %s", slug, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/{slug}",
    status_code=status.HTTP_200_OK,
    summary="Обновить документ",
    description="Частично обновляет заголовок или Markdown-содержимое документа.",
    operation_id="updateDocument",
    response_description="Обновлённый документ.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=DocumentDetailSchema,
)
async def update_document(
    slug: Annotated[str, Path(description="URL-идентификатор документа.")],
    data: DocumentUpdateSchema,
    documents_service: DocumentsServiceDep,
) -> DocumentDetailSchema:
    """Обновляет документ.

    Args:
        slug: URL-идентификатор документа.
        data: Изменяемые поля.
        documents_service: Сервис документов.

    Returns:
        Обновлённый документ.

    Raises:
        HTTPException: Если документ не найден или обновление не удалось.
    """
    logger.info("🚀 Запрос PATCH /documents/%s.", slug)
    try:
        result = await documents_service.update_document(
            slug=slug,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Документ slug=%s обновлён.", slug)
        return result
    except (DocumentNotFoundError, DocumentsServiceError) as error:
        logger.exception("❌ Ошибка PATCH /documents/%s. Детали: %s", slug, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить документ",
    description="Удаляет документ и все его связи.",
    operation_id="deleteDocument",
    response_description="Документ удалён.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_document(
    slug: Annotated[str, Path(description="URL-идентификатор документа.")],
    documents_service: DocumentsServiceDep,
) -> None:
    """Удаляет документ.

    Args:
        slug: URL-идентификатор документа.
        documents_service: Сервис документов.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если документ не найден или удаление не удалось.
    """
    logger.info("🚀 Запрос DELETE /documents/%s.", slug)
    try:
        await documents_service.delete_document(slug=slug)
        logger.info("✅ Документ slug=%s удалён.", slug)
    except (DocumentNotFoundError, DocumentsServiceError) as error:
        logger.exception("❌ Ошибка DELETE /documents/%s. Детали: %s", slug, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/{slug}/links",
    status_code=status.HTTP_200_OK,
    summary="Получить связи документа",
    description="Возвращает задачи канбана и узлы ИСР, связанные с документом.",
    operation_id="getDocumentLinks",
    response_description="Список целей, связанных с документом.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[LinkedTargetSchema],
)
async def get_document_links(
    slug: Annotated[str, Path(description="URL-идентификатор документа.")],
    document_links_service: DocumentLinksServiceDep,
) -> list[LinkedTargetSchema]:
    """Получает связи документа.

    Args:
        slug: URL-идентификатор документа.
        document_links_service: Сервис связей документов.

    Returns:
        Связанные задачи и узлы ИСР.

    Raises:
        HTTPException: Если документ не найден или связи получить не удалось.
    """
    logger.info("🚀 Запрос GET /documents/%s/links.", slug)
    try:
        result = await document_links_service.get_links_for_document_slug(slug=slug)
        logger.info("✅ Связи документа slug=%s получены. Найдено: %s.", slug, len(result))
        return result
    except (DocumentNotFoundError, DocumentLinksServiceError) as error:
        logger.exception("❌ Ошибка GET /documents/%s/links. Детали: %s", slug, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
