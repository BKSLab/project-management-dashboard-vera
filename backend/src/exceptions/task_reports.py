"""Ошибки отчёта по задаче."""

from src.exceptions.base import RepositoryError, ServiceError


class TaskReportsRepositoryError(RepositoryError):
    detail = "Не удалось сохранить или прочитать отчёт."


class TaskReportsServiceError(ServiceError):
    detail = "Не удалось обработать отчёт по задаче."


class TaskReportConflictError(TaskReportsServiceError):
    status_code = 409
    detail = "Отчёт или исходный комментарий изменился. Обновите данные перед сохранением."


class TaskReportSourceError(TaskReportsServiceError):
    status_code = 404
    detail = "Комментарий не принадлежит этой задаче или уже удалён."
