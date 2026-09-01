from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class ProjectsRepositoryError(RepositoryError):
    """Ошибка доступа к проектам."""

    detail = "Ошибка базы данных при обработке проектов."


class ProjectKeyAlreadyExistsRepositoryError(ProjectsRepositoryError):
    """Код проекта уже занят в базе данных."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(error_details=f"Код проекта {key} уже занят.")


class ProjectsServiceError(ServiceError):
    """Ошибка бизнес-операции с проектами."""

    detail = "Не удалось выполнить операцию с проектами."


class ProjectNotFoundError(ProjectsServiceError):
    """Проект не найден."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, project_id: int):
        self.project_id = project_id
        super().__init__(error_details=f"Проект id={project_id} не найден.")

    @property
    def detail(self) -> str:
        return f"Проект с id={self.project_id} не найден."


class ProjectKeyConflictError(ProjectsServiceError):
    """Код проекта уже используется другим проектом."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, key: str):
        self.key = key
        super().__init__(error_details=f"Код проекта {key} уже используется.")

    @property
    def detail(self) -> str:
        return f"Проект с кодом {self.key} уже существует."
