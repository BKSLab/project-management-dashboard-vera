"""Ошибки разрешения доступа к объектам проекта.

Доступ — бизнес-правило, а не деталь транспорта, поэтому у него собственные
доменные ошибки. Transport-слой только переводит их в HTTP-ответ.
"""

from fastapi import status

from src.exceptions.base import ServiceError


class AccessServiceError(ServiceError):
    """Ошибка проверки доступа к объекту проекта."""

    detail = "Ошибка проверки доступа."


class ResourceNotAvailableError(AccessServiceError):
    """Объект не существует либо не принадлежит доступному проекту.

    Оба случая намеренно неразличимы: иначе перебором идентификаторов
    выяснялось бы существование чужих проектов и задач.
    """

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Объект не найден."

    def __init__(self, *, resource: str, resource_id: int) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(error_details=f"{resource} id={resource_id} недоступен пользователю.")


class ProjectOwnerRequiredError(AccessServiceError):
    """Действие доступно только владельцу проекта."""

    status_code = status.HTTP_403_FORBIDDEN
    detail = "Действие доступно только владельцу проекта."

    def __init__(self, *, project_id: int) -> None:
        self.project_id = project_id
        super().__init__(error_details=f"Требуется роль владельца проекта id={project_id}.")
