from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class WbsNodesRepositoryError(RepositoryError):
    """Ошибка доступа к узлам ИСР."""

    detail = "Ошибка базы данных при обработке структуры ИСР."


class WbsNodesServiceError(ServiceError):
    """Ошибка бизнес-операции со структурой ИСР."""

    detail = "Не удалось выполнить операцию со структурой ИСР."


class WbsNodeNotFoundError(WbsNodesServiceError):
    """Узел ИСР не найден."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, node_id: int):
        self.node_id = node_id
        super().__init__(error_details=f"Узел ИСР id={node_id} не найден.")

    @property
    def detail(self) -> str:
        return f"Раздел ИСР с id={self.node_id} не найден."


class WbsNodeForeignProjectError(WbsNodesServiceError):
    """Узел ИСР принадлежит другому проекту."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, node_id: int, project_id: int):
        self.node_id = node_id
        self.project_id = project_id
        super().__init__(
            error_details=f"Узел ИСР id={node_id} не принадлежит проекту id={project_id}.",
        )

    @property
    def detail(self) -> str:
        return f"Раздел ИСР с id={self.node_id} принадлежит другому проекту."


class WbsNodeCycleError(WbsNodesServiceError):
    """Перемещение узла создало бы цикл в структуре."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, node_id: int, parent_id: int):
        self.node_id = node_id
        self.parent_id = parent_id
        super().__init__(
            error_details=f"Узел id={node_id} нельзя перенести внутрь id={parent_id}.",
        )

    @property
    def detail(self) -> str:
        return "Раздел нельзя перенести внутрь самого себя или собственного подраздела."
