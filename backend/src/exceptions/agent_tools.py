from src.exceptions.base import RepositoryError, ServiceError


class AgentToolRunsRepositoryError(RepositoryError):
    """Ошибка журнала действий."""


class AgentToolsServiceError(ServiceError):
    """Безопасная ошибка выполнения инструмента."""

    status_code = 500
    detail = "Не удалось выполнить действие агента."


class AgentToolAccessError(AgentToolsServiceError):
    """Объект недоступен в серверной области проекта."""

    status_code = 404
    detail = "Объект или действие недоступны в этом проекте."


class AgentToolConflictError(AgentToolsServiceError):
    """Действие нельзя выполнить с указанным состоянием или ключом."""

    status_code = 409
    detail = "Состояние изменилось. Уточните действие по текущим данным."


class AgentToolOperationError(AgentToolsServiceError):
    """Сохраняет безопасный контракт ошибки доменного сценария."""

    def __init__(self, error: ServiceError) -> None:
        super().__init__(str(error))
        self.status_code = error.status_code
        self.detail = error.detail
