from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class DocumentsRepositoryError(RepositoryError):
    """Ошибка доступа к данным документов."""

    detail = "Ошибка базы данных при обработке документов."


class DocumentSlugAlreadyExistsRepositoryError(DocumentsRepositoryError):
    """Ошибка уникальности slug внутри проекта на уровне базы данных."""

    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(error_details=f"Документ со slug={slug!r} уже существует в проекте.")


class DocumentsServiceError(ServiceError):
    """Ошибка бизнес-операции с документами."""

    detail = "Не удалось выполнить операцию с документами."


class DocumentNotFoundError(DocumentsServiceError):
    """Документ не найден."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, document_id: int):
        self.document_id = document_id
        super().__init__(error_details=f"Документ id={document_id} не найден.")

    @property
    def detail(self) -> str:
        return f"Документ с id={self.document_id} не найден."


class DocumentSlugConflictError(DocumentsServiceError):
    """Документ с указанным slug уже существует в проекте."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(error_details=f"Документ со slug={slug!r} уже существует в проекте.")

    @property
    def detail(self) -> str:
        return f"Документ со slug='{self.slug}' уже существует в этом проекте."
