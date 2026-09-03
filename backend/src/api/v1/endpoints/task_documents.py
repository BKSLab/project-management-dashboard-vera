import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status

from src.api.v1.responses import NOT_FOUND_RESPONSE, SERVER_ERROR_RESPONSE, VALIDATION_RESPONSE
from src.dependencies.access import get_accessible_task
from src.dependencies.auth import CurrentUserDep
from src.dependencies.services import TaskDocumentImportServiceDep
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.documents import DocumentsServiceError
from src.exceptions.knowledge import KnowledgeProviderError
from src.exceptions.task_attachments import TaskAttachmentsServiceError
from src.exceptions.tasks import TasksServiceError
from src.schemas.task_documents import TaskDocumentImportSchema

router = APIRouter(tags=["task-documents"])
logger = logging.getLogger(__name__)


@router.post(
    path="/tasks/{task_id}/documents/import",
    dependencies=[Depends(get_accessible_task)],
    status_code=status.HTTP_201_CREATED,
    summary="Импортировать документ в задачу",
    description=(
        "Сохраняет исходный файл в задаче, извлекает его текст, создаёт документ "
        "проекта и сразу связывает его с задачей."
    ),
    operation_id="importTaskDocument",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=TaskDocumentImportSchema,
)
async def import_task_document(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи.")],
    file: Annotated[UploadFile, File(description="Документ размером до 10 МБ.")],
    user: CurrentUserDep,
    service: TaskDocumentImportServiceDep,
) -> TaskDocumentImportSchema:
    """Импортирует один новый документ и связывает его с задачей."""
    try:
        content = await file.read(service.max_file_size + 1)
        return await service.import_file(
            task_id=task_id,
            user_id=user.id,
            file_name=file.filename or "",
            content_type=file.content_type,
            content=content,
        )
    except (
        TaskAttachmentsServiceError,
        TasksServiceError,
        DocumentsServiceError,
        DocumentLinksServiceError,
        KnowledgeProviderError,
    ) as error:
        logger.exception("❌ Ошибка импорта документа в задачу id=%s.", task_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    finally:
        await file.close()
