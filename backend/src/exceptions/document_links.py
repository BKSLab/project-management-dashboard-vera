from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class DocumentLinksRepositoryError(RepositoryError):
    """Ошибка доступа к данным связей документов."""

    detail = "Ошибка базы данных при обработке связей документов."


class DocumentLinkAlreadyExistsRepositoryError(DocumentLinksRepositoryError):
    """Такая связь документа уже существует в БД."""

    def __init__(self, document_id: int):
        self.document_id = document_id
        super().__init__(error_details=f"Связь документа id={document_id} уже существует.")


class DocumentLinksServiceError(ServiceError):
    """Ошибка бизнес-операции со связями документов."""

    detail = "Не удалось выполнить операцию со связью документа."


class DocumentLinkAlreadyExistsError(DocumentLinksServiceError):
    """Такая связь документа уже существует."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, document_id: int):
        self.document_id = document_id
        super().__init__(error_details=f"Связь документа id={document_id} уже существует.")

    @property
    def detail(self) -> str:
        return f"Такая связь документа с id={self.document_id} уже существует."


class DocumentLinkProjectMismatchError(DocumentLinksServiceError):
    """Документ и задача принадлежат разным проектам."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, document_id: int, task_id: int):
        self.document_id = document_id
        self.task_id = task_id
        super().__init__(
            error_details=(
                f"Документ id={document_id} и задача id={task_id} принадлежат разным проектам."
            ),
        )

    @property
    def detail(self) -> str:
        return "Связать можно только документ и задачу одного проекта."


class DocumentLinkNotFoundError(DocumentLinksServiceError):
    """Связь документа не найдена."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, link_id: int):
        self.link_id = link_id
        super().__init__(error_details=f"Связь документа id={link_id} не найдена.")

    @property
    def detail(self) -> str:
        return f"Связь документа с id={self.link_id} не найдена."
