from fastapi import status

from src.exceptions.base import ApplicationError, RepositoryError, ServiceError


class TaskAttachmentsRepositoryError(RepositoryError):
    """Ошибка доступа к метаданным файлов задач."""

    detail = "Ошибка базы данных при обработке файлов задачи."


class TaskAttachmentStorageError(ApplicationError):
    """Ошибка локального файлового хранилища."""

    detail = "Не удалось выполнить операцию с файловым хранилищем."


class TaskAttachmentsServiceError(ServiceError):
    """Ошибка бизнес-операции с файлами задач."""

    detail = "Не удалось выполнить операцию с файлами задачи."


class TaskAttachmentNotFoundError(TaskAttachmentsServiceError):
    """Файл задачи не найден."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, attachment_id: int) -> None:
        self.attachment_id = attachment_id
        super().__init__(error_details=f"Файл задачи id={attachment_id} не найден.")

    @property
    def detail(self) -> str:
        return f"Файл задачи с id={self.attachment_id} не найден."


class TaskAttachmentValidationError(TaskAttachmentsServiceError):
    """Файл задачи не прошёл валидацию."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

    def __init__(self, detail: str) -> None:
        self.validation_detail = detail
        super().__init__(error_details=detail)

    @property
    def detail(self) -> str:
        return self.validation_detail


class TaskAttachmentTooLargeError(TaskAttachmentsServiceError):
    """Размер файла превышает допустимый лимит."""

    status_code = status.HTTP_413_CONTENT_TOO_LARGE

    def __init__(self, max_size_mb: int) -> None:
        self.max_size_mb = max_size_mb
        super().__init__(error_details=f"Размер файла превышает {max_size_mb} МБ.")

    @property
    def detail(self) -> str:
        return f"Размер файла превышает допустимые {self.max_size_mb} МБ."


class TaskAttachmentUnsupportedTypeError(TaskAttachmentsServiceError):
    """Расширение файла не входит в разрешённый список."""

    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    def __init__(self, extension: str) -> None:
        self.extension = extension or "без расширения"
        super().__init__(error_details=f"Неподдерживаемый тип файла: {self.extension}.")

    @property
    def detail(self) -> str:
        return f"Файлы типа {self.extension} не поддерживаются."


class TaskAttachmentLimitError(TaskAttachmentsServiceError):
    """Задача достигла лимита количества файлов."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, max_files: int) -> None:
        self.max_files = max_files
        super().__init__(error_details=f"Достигнут лимит {max_files} файлов на задачу.")

    @property
    def detail(self) -> str:
        return f"К задаче можно прикрепить не более {self.max_files} файлов."


class TaskDocumentImportError(TaskAttachmentsServiceError):
    """Файл нельзя преобразовать в документ проекта."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

    def __init__(self, detail: str) -> None:
        self.import_detail = detail
        super().__init__(error_details=detail)

    @property
    def detail(self) -> str:
        return self.import_detail
