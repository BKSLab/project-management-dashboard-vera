from fastapi import status


class ServiceError(Exception):
    """Базовое исключение для ошибок слоя сервисов."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, error_details: str):
        self.error_details = error_details
        super().__init__(self.error_details)

    def __str__(self) -> str:
        return f"Ошибка в {self.__class__.__name__}. Подробности: {self.error_details}"

    @property
    def detail(self) -> str:
        return self.error_details


class DocumentNotFoundError(ServiceError):
    """Документ не найден."""
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, slug: str):
        super().__init__(f"Документ со slug='{slug}' не найден.")


class DocumentSlugConflictError(ServiceError):
    """Документ с таким slug уже существует."""
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, slug: str):
        super().__init__(f"Документ со slug='{slug}' уже существует.")


class WbsItemNotFoundError(ServiceError):
    """Узел ИСР не найден."""
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, item_id: int):
        super().__init__(f"Узел ИСР с id={item_id} не найден.")


class KanbanStageNotFoundError(ServiceError):
    """Стадия канбана не найдена."""
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, stage_id: int):
        super().__init__(f"Стадия канбана с id={stage_id} не найдена.")


class KanbanStageHasTasksError(ServiceError):
    """Удаление стадии, в которой есть задачи."""
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, stage_id: int):
        super().__init__(f"Стадия канбана с id={stage_id} содержит задачи и не может быть удалена.")


class KanbanTaskNotFoundError(ServiceError):
    """Задача канбана не найдена."""
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, task_id: int):
        super().__init__(f"Задача канбана с id={task_id} не найдена.")


class KanbanTaskFromWbsDeleteError(ServiceError):
    """Удаление листовой задачи ИСР запрещено."""
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, task_id: int):
        super().__init__(
            f"Задача с id={task_id} связана с узлом ИСР и не может быть удалена, только перемещена."
        )


class TaskCommentNotFoundError(ServiceError):
    """Комментарий не найден."""
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, comment_id: int):
        super().__init__(f"Комментарий с id={comment_id} не найден.")


class DocumentLinkInvalidError(ServiceError):
    """Связь документа должна указывать ровно один объект."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    def __init__(self):
        super().__init__(
            "Должно быть заполнено ровно одно из полей: kanban_task_id или wbs_item_id."
        )


class DocumentLinkNotFoundError(ServiceError):
    """Связь документа не найдена."""
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, link_id: int):
        super().__init__(f"Связь документа с id={link_id} не найдена.")
