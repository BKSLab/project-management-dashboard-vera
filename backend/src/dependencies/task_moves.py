"""Общий HTTP-сервис task_moves."""

from src.dependencies.services import TaskMovesServiceDep, get_task_moves_service

__all__ = ["TaskMovesServiceDep", "get_task_moves_service"]
