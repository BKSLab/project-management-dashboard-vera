import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from fastapi.responses import FileResponse

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.access import require_task_access
from src.dependencies.auth import AuthorizationHeaderDep, SessionCookieDep, require_write_scope
from src.dependencies.scopes import AttachmentDownloadServiceDep
from src.dependencies.services import TaskAttachmentsServiceDep
from src.exceptions.task_attachments import TaskAttachmentsServiceError
from src.exceptions.tasks import TasksServiceError
from src.schemas.task_attachments import TaskAttachmentSchema
from src.services.attachment_download import DOWNLOAD_ERRORS
from src.utils.api_tokens import extract_bearer_secret

router = APIRouter(prefix="", tags=["task-attachments"])
logger = logging.getLogger(__name__)

TOO_LARGE_RESPONSE = {
    "description": "Размер файла превышает установленный лимит.",
    "content": {"application/json": {"example": {"detail": "Размер файла превышает 10 МБ."}}},
}
UNSUPPORTED_TYPE_RESPONSE = {
    "description": "Тип файла не входит в разрешённый список.",
    "content": {"application/json": {"example": {"detail": "Тип файла не поддерживается."}}},
}


@router.get(
    path="/tasks/{task_id}/attachments",
    dependencies=[Depends(require_task_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить файлы задачи",
    description="Возвращает метаданные всех файлов задачи в хронологическом порядке.",
    operation_id="getTaskAttachments",
    response_description="Список файлов задачи.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[TaskAttachmentSchema],
)
async def get_task_attachments(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    service: TaskAttachmentsServiceDep,
) -> list[TaskAttachmentSchema]:
    """Получает файлы задачи.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис файлов задач.

    Returns:
        Метаданные прикреплённых файлов.

    Raises:
        HTTPException: Если задача не найдена или получить файлы не удалось.
    """
    logger.info("🚀 Запрос GET /tasks/%s/attachments.", task_id)
    try:
        result = await service.get_attachments(task_id=task_id)
        logger.info("✅ Файлы задачи id=%s получены. Найдено: %s.", task_id, len(result))
        return result
    except (TaskAttachmentsServiceError, TasksServiceError) as error:
        logger.exception("❌ Ошибка получения файлов задачи id=%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/tasks/{task_id}/attachments",
    dependencies=[Depends(require_write_scope), Depends(require_task_access)],
    status_code=status.HTTP_201_CREATED,
    summary="Прикрепить файл к задаче",
    description="Проверяет и сохраняет один multipart-файл размером до 10 МБ.",
    operation_id="uploadTaskAttachment",
    response_description="Метаданные созданного файла.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        413: TOO_LARGE_RESPONSE,
        415: UNSUPPORTED_TYPE_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=TaskAttachmentSchema,
)
async def upload_task_attachment(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    file: Annotated[UploadFile, File(description="Файл задачи размером до 10 МБ.")],
    service: TaskAttachmentsServiceDep,
) -> TaskAttachmentSchema:
    """Прикрепляет multipart-файл к задаче.

    Args:
        task_id: Идентификатор задачи.
        file: Загружаемый файл.
        service: Сервис файлов задач.

    Returns:
        Метаданные созданного файла.

    Raises:
        HTTPException: Если задача не найдена, файл невалиден или сохранение не удалось.
    """
    logger.info("🚀 Запрос POST /tasks/%s/attachments. Файл: %r.", task_id, file.filename)
    try:
        content = await file.read(service.max_file_size + 1)
        result = await service.upload_attachment(
            task_id=task_id,
            file_name=file.filename or "",
            content_type=file.content_type,
            content=content,
        )
        logger.info("✅ Файл id=%s добавлен к задаче id=%s.", result.id, task_id)
        return result
    except (TaskAttachmentsServiceError, TasksServiceError) as error:
        logger.exception("❌ Ошибка загрузки файла задачи id=%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    finally:
        await file.close()


@router.get(
    path="/tasks/{task_id}/attachments/{attachment_id}/content",
    status_code=status.HTTP_200_OK,
    summary="Открыть или скачать файл задачи",
    description="Показывает безопасное растровое изображение inline, остальные файлы скачивает.",
    operation_id="getTaskAttachmentContent",
    response_description="Бинарное содержимое файла.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def get_task_attachment_content(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    attachment_id: Annotated[int, Path(gt=0, description="Идентификатор файла задачи.")],
    service: AttachmentDownloadServiceDep,
    session_cookie: SessionCookieDep = None,
    authorization: AuthorizationHeaderDep = None,
) -> FileResponse:
    """Возвращает физическое содержимое файла.

    Аутентификация, проверка доступа и чтение метаданных выполняются в
    короткой области базы внутри сервиса. В графе зависимостей маршрута
    нет ни `DbSessionDep`, ни построенных на ней зависимостей: иначе
    медленное скачивание удерживало бы соединение с PostgreSQL всё время
    передачи файла.

    Args:
        task_id: Идентификатор задачи.
        attachment_id: Идентификатор файла.
        service: Подготовка выдачи файла.
        session_cookie: Значение cookie сессии.
        authorization: Заголовок ``Authorization`` внешнего клиента.

    Returns:
        Потоковый файловый HTTP-ответ.

    Raises:
        HTTPException: Если файл не найден или недоступен.
    """
    logger.info(
        "🚀 Запрос GET /tasks/%s/attachments/%s/content.",
        task_id,
        attachment_id,
    )
    try:
        download = await service.prepare(
            task_id=task_id,
            attachment_id=attachment_id,
            session_token=session_cookie,
            bearer_secret=extract_bearer_secret(authorization),
        )
    except DOWNLOAD_ERRORS as error:
        logger.info("ℹ️ Выдача файла id=%s отклонена: %s.", attachment_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    logger.info("✅ Содержимое файла id=%s подготовлено.", attachment_id)
    # Дальше начинается долгоживущая фаза: наружу уходят только
    # неизменяемые значения, ни одной ссылки на состояние базы.
    return FileResponse(
        path=download.path,
        media_type=download.media_type,
        filename=download.filename,
        content_disposition_type=download.disposition,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete(
    path="/tasks/{task_id}/attachments/{attachment_id}",
    dependencies=[Depends(require_write_scope), Depends(require_task_access)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить файл задачи",
    description="Удаляет метаданные и физическое содержимое файла.",
    operation_id="deleteTaskAttachment",
    response_description="Файл удалён.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_task_attachment(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    attachment_id: Annotated[int, Path(gt=0, description="Идентификатор файла задачи.")],
    service: TaskAttachmentsServiceDep,
) -> None:
    """Удаляет файл задачи.

    Args:
        task_id: Идентификатор задачи.
        attachment_id: Идентификатор файла.
        service: Сервис файлов задач.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если файл не найден или удалить его не удалось.
    """
    logger.info("🚀 Запрос DELETE /tasks/%s/attachments/%s.", task_id, attachment_id)
    try:
        await service.delete_attachment(task_id=task_id, attachment_id=attachment_id)
        logger.info("✅ Файл id=%s удалён из задачи id=%s.", attachment_id, task_id)
    except TaskAttachmentsServiceError as error:
        logger.exception("❌ Ошибка удаления файла id=%s. Детали: %s", attachment_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
