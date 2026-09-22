from src.exceptions.base import RepositoryError, ServiceError


class AgentConversationsRepositoryError(RepositoryError):
    """Ошибка хранения диалогов."""


class AgentMessagesRepositoryError(RepositoryError):
    """Ошибка хранения реплик и очереди ответов."""


class AgentConversationsServiceError(ServiceError):
    """Ошибка сценария общения с агентом."""

    detail = "Не удалось обработать диалог. Попробуйте ещё раз."


class AgentConversationNotFoundError(AgentConversationsServiceError):
    """Диалог отсутствует или недоступен участнику."""

    status_code = 404
    detail = "Диалог не найден."


class AgentConversationBusyError(AgentConversationsServiceError):
    """Предыдущий вопрос ещё обрабатывается."""

    status_code = 409
    detail = "Дождитесь ответа на предыдущий вопрос в этом диалоге."


class AgentMessageConflictError(AgentConversationsServiceError):
    """Повтор запроса не соответствует сохранённой операции."""

    status_code = 409
    detail = "Сообщение уже изменилось. Обновите диалог и повторите действие."
