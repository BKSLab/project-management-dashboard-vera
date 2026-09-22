"""Ошибки хранения, сценариев и realtime-транспорта чата."""

from src.exceptions.base import RepositoryError, ServiceError


class ChatRepositoryError(RepositoryError):
    """Ошибка PostgreSQL в контуре чата."""


class ChatServiceError(ServiceError):
    """Не удалось выполнить операцию чата."""

    detail = "Не удалось выполнить операцию чата."


class ChatNotFoundError(ChatServiceError):
    """Объект отсутствует или недоступен участнику."""

    status_code = 404
    detail = "Чат или объект сообщения недоступен."


class ChatForbiddenError(ChatServiceError):
    """Изменять чужое сообщение нельзя."""

    status_code = 403
    detail = "Недостаточно прав для действия в чате."


class ChatValidationError(ChatServiceError):
    """Содержимое нарушает контракт чата."""

    status_code = 422
    detail = "Проверьте текст, участников, ссылки и вложения сообщения."


class ChatConflictError(ChatServiceError):
    """Сообщение изменилось либо файл уже отправлен."""

    status_code = 409
    detail = "Данные изменились. Обновите сообщение и повторите действие."


class ChatUnavailableError(ChatServiceError):
    """Координатор временно недоступен; клиент переподключится."""

    status_code = 503
    detail = "Связь с чатом временно недоступна. Повторите отправку."


class ChatRateLimitError(ChatServiceError):
    """Превышен общий для всех экземпляров приложения лимит."""

    status_code = 429
    detail = "Слишком много действий. Подождите немного и повторите."
