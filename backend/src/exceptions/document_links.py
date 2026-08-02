from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class DocumentLinksRepositoryError(RepositoryError):
    """Ошибка доступа к данным связей документов."""

    detail = "Ошибка базы данных при обработке связей документов."


class DocumentLinksServiceError(ServiceError):
    """Ошибка бизнес-операции со связями документов."""

    detail = "Не удалось выполнить операцию со связью документа."


class DocumentLinkAlreadyExistsRepositoryError(DocumentLinksRepositoryError):
    """Такая связь документа уже существует в БД."""

    def __init__(self, document_id: int):
        self.document_id = document_id
        super().__init__(error_details=f"Связь документа id={document_id} уже существует.")


class DocumentLinkAlreadyExistsError(DocumentLinksServiceError):
    """Такая связь документа уже существует."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, document_id: int):
        self.document_id = document_id
        super().__init__(error_details=f"Связь документа id={document_id} уже существует.")

    @property
    def detail(self) -> str:
        return f"Такая связь документа с id={self.document_id} уже существует."


class DocumentLinkInvalidError(DocumentLinksServiceError):
    """Связь указывает не на один целевой объект."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Должно быть заполнено ровно одно из полей: kanban_task_id или wbs_item_id."

    def __init__(self):
        super().__init__(error_details=self.detail)


class DocumentLinkNotFoundError(DocumentLinksServiceError):
    """Связь документа не найдена."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, link_id: int):
        self.link_id = link_id
        super().__init__(error_details=f"Связь документа id={link_id} не найдена.")

    @property
    def detail(self) -> str:
        return f"Связь документа с id={self.link_id} не найдена."
