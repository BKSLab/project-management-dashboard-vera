import logging

from fastapi import APIRouter, HTTPException, status

from src.dependencies.services import DocumentLinksServiceDep, DocumentsServiceDep
from src.exceptions.repositories import DocumentLinksRepositoryError, DocumentsRepositoryError
from src.exceptions.services import DocumentNotFoundError
from src.schemas.document_links import LinkedTargetSchema
from src.schemas.documents import (
    DocumentCreateSchema,
    DocumentDetailSchema,
    DocumentSchema,
    DocumentUpdateSchema,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    path="",
    status_code=status.HTTP_200_OK,
    summary="Список документов",
    response_model=list[DocumentSchema],
)
async def get_documents(documents_service: DocumentsServiceDep):
    try:
        return await documents_service.get_document_list()
    except DocumentsRepositoryError as error:
        logger.exception("❌ Ошибка при получении списка документов. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать документ",
    response_model=DocumentDetailSchema,
)
async def create_document(data: DocumentCreateSchema, documents_service: DocumentsServiceDep):
    try:
        return await documents_service.create_document(
            title=data.title, slug=data.slug, content_md=data.content_md
        )
    except DocumentsRepositoryError as error:
        logger.exception("❌ Ошибка при создании документа. %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.get(
    path="/{slug}",
    status_code=status.HTTP_200_OK,
    summary="Документ по slug",
    response_model=DocumentDetailSchema,
)
async def get_document(slug: str, documents_service: DocumentsServiceDep):
    try:
        return await documents_service.get_document_by_slug(slug=slug)
    except (DocumentsRepositoryError, DocumentNotFoundError) as error:
        logger.exception("❌ Ошибка при получении документа. slug=%s. %s", slug, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.patch(
    path="/{slug}",
    status_code=status.HTTP_200_OK,
    summary="Обновить документ",
    response_model=DocumentDetailSchema,
)
async def update_document(
    slug: str,
    data: DocumentUpdateSchema,
    documents_service: DocumentsServiceDep,
):
    try:
        return await documents_service.update_document(
            slug=slug,
            data=data.model_dump(exclude_unset=True),
        )
    except (DocumentsRepositoryError, DocumentNotFoundError) as error:
        logger.exception("❌ Ошибка при обновлении документа. slug=%s. %s", slug, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.delete(
    path="/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить документ",
)
async def delete_document(slug: str, documents_service: DocumentsServiceDep):
    try:
        await documents_service.delete_document(slug=slug)
    except (DocumentsRepositoryError, DocumentNotFoundError) as error:
        logger.exception("❌ Ошибка при удалении документа. slug=%s. %s", slug, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.get(
    path="/{slug}/links",
    status_code=status.HTTP_200_OK,
    summary="Связанные задачи/узлы ИСР для документа",
    response_model=list[LinkedTargetSchema],
)
async def get_document_links(
    slug: str,
    documents_service: DocumentsServiceDep,
    document_links_service: DocumentLinksServiceDep,
):
    try:
        document = await documents_service.get_document_by_slug(slug=slug)
        return await document_links_service.get_links_for_document(document_id=document.id)
    except (DocumentsRepositoryError, DocumentNotFoundError, DocumentLinksRepositoryError) as error:
        logger.exception("❌ Ошибка при получении связей документа. slug=%s. %s", slug, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)
