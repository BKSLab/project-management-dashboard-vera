from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class KnowledgeIndexJobsRepositoryError(RepositoryError):
    """Ошибка постоянной очереди индексации."""

    detail = "Ошибка очереди индексации базы знаний."


class KnowledgeServiceError(ServiceError):
    """Общая ошибка базы знаний проекта."""

    detail = "Не удалось выполнить операцию с базой знаний проекта."


class KnowledgeEventsServiceError(KnowledgeServiceError):
    """Ошибка записи доменного события в outbox."""

    detail = "Не удалось поставить изменение в очередь базы знаний."


class KnowledgeProviderError(KnowledgeServiceError):
    """Ошибка Qdrant, embedding API или LLM API."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "AI-сервис временно недоступен. Повторите попытку позже."


class KnowledgeDisabledError(KnowledgeServiceError):
    """AI-база явно отключена конфигурацией приложения."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "AI-база проектов отключена в конфигурации приложения."


class ProjectAgentError(KnowledgeServiceError):
    """Ошибка формирования ответа Project Agent."""

    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "Project Agent не смог сформировать ответ."
