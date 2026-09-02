from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class MilestonesRepositoryError(RepositoryError):
    """Ошибка доступа к проектным вехам."""

    detail = "Ошибка базы данных при обработке вех."


class MilestonesServiceError(ServiceError):
    """Ошибка бизнес-операции с проектными вехами."""

    detail = "Не удалось выполнить операцию с вехами."


class MilestoneNotFoundError(MilestonesServiceError):
    """Веха не найдена в указанном проекте."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, milestone_id: int):
        self.milestone_id = milestone_id
        super().__init__(error_details=f"Веха id={milestone_id} не найдена.")

    @property
    def detail(self) -> str:
        return f"Веха с id={self.milestone_id} не найдена."
