"""Доменные ошибки редактора досок."""

from src.exceptions.project_boards import ProjectBoardsServiceError


class BoardEditorValidationError(ProjectBoardsServiceError):
    status_code = 422
    detail = "Объекты metadata должны принадлежать этой доске."


class BoardAlreadyPromotedError(ProjectBoardsServiceError):
    status_code = 409
    detail = "Доска уже привязана к проекту."


class BoardObjectLockedError(ProjectBoardsServiceError):
    status_code = 409
    detail = "Объект заблокирован в редакторе. Сначала снимите блокировку."
