from src.exceptions.base import RepositoryError, ServiceError


class ProjectRiskRepositoryError(RepositoryError):
    """Ошибка доступа к реестру рисков."""

    detail = "Ошибка базы данных при обработке рисков проекта."


class ProjectRiskServiceError(ServiceError):
    """Ошибка сценария управления риском."""

    detail = "Не удалось выполнить операцию с рисками проекта."


class ProjectRiskNotFoundError(ProjectRiskServiceError):
    """Риск отсутствует в указанном проекте."""

    status_code = 404
    detail = "Риск не найден."

    def __init__(self, risk_id: int) -> None:
        self.risk_id = risk_id
        super().__init__(f"Риск id={risk_id} не найден в проекте запроса.")


class ProjectRiskTaskMismatchError(ProjectRiskServiceError):
    """Задача отсутствует в текущем проекте."""

    status_code = 422
    detail = "Выберите существующую задачу этого проекта."

    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(f"Задача id={task_id} недоступна для связи с риском.")


class ProjectRiskOwnerMismatchError(ProjectRiskServiceError):
    """Ответственный не входит в команду проекта."""

    status_code = 422
    detail = "Ответственный должен быть участником этого проекта."

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        super().__init__(f"Пользователь id={user_id} не входит в проект риска.")
