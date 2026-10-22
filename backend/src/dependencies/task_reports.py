"""Общий HTTP-сервис task_reports."""

from src.dependencies.services import TaskReportsServiceDep, get_task_reports_service

__all__ = ["TaskReportsServiceDep", "get_task_reports_service"]
