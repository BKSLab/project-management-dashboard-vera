"""Исключения составного импорта документа в задачу.

У верхнего сервиса своя иерархия ошибок: эндпоинту не нужно знать, из
скольких вложенных сервисов он собран, и перечислять их семейства.
"""

from fastapi import status

from src.exceptions.base import ServiceError


class TaskDocumentImportServiceError(ServiceError):
    """Базовая ошибка импорта документа в задачу."""

    detail = "Не удалось импортировать документ в задачу."


class TaskDocumentTaskNotFoundError(TaskDocumentImportServiceError):
    """Задача, в которую импортируют документ, не найдена."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(error_details=f"Задача id={task_id} не найдена.")

    @property
    def detail(self) -> str:
        return f"Задача с id={self.task_id} не найдена."


class TaskDocumentValidationError(TaskDocumentImportServiceError):
    """Файл не прошёл проверку до начала импорта."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

    def __init__(self, detail: str) -> None:
        self.validation_detail = detail
        super().__init__(error_details=detail)

    @property
    def detail(self) -> str:
        return self.validation_detail


class TaskDocumentTooLargeError(TaskDocumentImportServiceError):
    """Размер файла превышает допустимый лимит."""

    status_code = status.HTTP_413_CONTENT_TOO_LARGE

    def __init__(self, max_size_mb: int) -> None:
        self.max_size_mb = max_size_mb
        super().__init__(error_details=f"Размер файла превышает {max_size_mb} МБ.")

    @property
    def detail(self) -> str:
        return f"Размер файла превышает допустимые {self.max_size_mb} МБ."


class TaskDocumentUnsupportedFormatError(TaskDocumentImportServiceError):
    """Формат файла нельзя преобразовать в документ проекта."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

    def __init__(self, detail: str) -> None:
        self.format_detail = detail
        super().__init__(error_details=detail)

    @property
    def detail(self) -> str:
        return self.format_detail


class TaskDocumentStepFailedError(TaskDocumentImportServiceError):
    """Отказал один из вложенных шагов импорта.

    Причина отказа принадлежит вложенному сервису, но пользователю нужна
    именно она: «файл слишком большой» и «конфликт slug» — разные ситуации,
    и обобщать их до одного сообщения значило бы ухудшить ответ. Поэтому
    ошибка верхнего слоя переносит наружу статус и формулировку причины,
    оставаясь при этом единственной иерархией, которую знает эндпоинт.
    """

    def __init__(self, cause: ServiceError) -> None:
        self.cause_status_code = cause.status_code
        self.cause_detail = cause.detail
        super().__init__(error_details=f"{type(cause).__name__}: {cause.error_details}")

    @property
    def status_code(self) -> int:
        """Статус причины отказа."""
        return self.cause_status_code

    @property
    def detail(self) -> str:
        """Формулировка причины отказа."""
        return self.cause_detail
