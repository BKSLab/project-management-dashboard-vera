from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class KanbanStagesRepositoryError(RepositoryError):
    """Ошибка доступа к стадиям канбана."""

    detail = "Ошибка базы данных при обработке стадий канбана."


class KanbanStagesServiceError(ServiceError):
    """Ошибка бизнес-операции со стадиями канбана."""

    detail = "Не удалось выполнить операцию со стадиями канбана."


class KanbanStageNotFoundError(KanbanStagesServiceError):
    """Стадия канбана не найдена."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, stage_id: int):
        self.stage_id = stage_id
        super().__init__(error_details=f"Стадия канбана id={stage_id} не найдена.")

    @property
    def detail(self) -> str:
        return f"Стадия канбана с id={self.stage_id} не найдена."


class KanbanStageHasTasksError(KanbanStagesServiceError):
    """Стадия содержит задачи и не может быть удалена."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, stage_id: int):
        self.stage_id = stage_id
        super().__init__(error_details=f"Стадия id={stage_id} содержит задачи.")

    @property
    def detail(self) -> str:
        return f"Стадия канбана с id={self.stage_id} содержит задачи и не может быть удалена."
