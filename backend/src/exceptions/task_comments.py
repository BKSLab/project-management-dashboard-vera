from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class TaskCommentsRepositoryError(RepositoryError):
    """Ошибка доступа к комментариям задач."""

    detail = "Ошибка базы данных при обработке комментариев задач."


class TaskCommentsServiceError(ServiceError):
    """Ошибка бизнес-операции с комментариями задач."""

    detail = "Не удалось выполнить операцию с комментариями задачи."


class TaskCommentConflictError(TaskCommentsServiceError):
    """Прочитанная версия комментария больше не актуальна."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Комментарий изменён или удалён другим участником. Перечитайте его перед правкой."


class TaskCommentNotFoundError(TaskCommentsServiceError):
    """Комментарий задачи не найден."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, comment_id: int):
        self.comment_id = comment_id
        super().__init__(error_details=f"Комментарий id={comment_id} не найден.")

    @property
    def detail(self) -> str:
        return f"Комментарий с id={self.comment_id} не найден."
