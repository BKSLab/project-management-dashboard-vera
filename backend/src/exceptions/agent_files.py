from src.exceptions.base import RepositoryError, ServiceError


class AgentFilesRepositoryError(RepositoryError):
    """Ошибка хранения приватных загрузок."""


class AgentFilesServiceError(ServiceError):
    """Не удалось выполнить сценарий загрузки файла."""

    status_code = 500
    detail = "Не удалось обработать файл диалога."


class AgentFileNotFoundError(AgentFilesServiceError):
    """Файл или диалог не принадлежат участнику текущего проекта."""

    status_code = 404
    detail = "Файл или диалог недоступен."


class AgentFileConflictError(AgentFilesServiceError):
    """Нельзя удалить отправленный файл или превысить лимит диалога."""

    status_code = 409
    detail = "Отправленный файл нельзя удалить; в диалоге допускается не более 20 загрузок."


class AgentFileValidationError(AgentFilesServiceError):
    """Файл не соответствует общим ограничениям вложений задач."""

    status_code = 422
    detail = "Проверьте файл: допустимый формат, непустое содержимое и размер до 10 МБ."
