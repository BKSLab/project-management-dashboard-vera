"""Компактное представление сущностей трекера для MCP-инструментов.

Наружу отдаются отображаемые ключи (``PROJ-142``), а не числовые
идентификаторы: агент оперирует тем же, что видит человек в интерфейсе.
Длинные тексты обрезаются с явной пометкой, иначе один вызов инструмента
способен занять весь контекст вызывающей модели.

На вход принимаются DTO сервисного слоя, а не ORM-модели: представление
не должно зависеть от того, как данные хранятся.
"""

from src.services.project_query import (
    CommentDto,
    ProjectOverviewDto,
    ProjectSummaryDto,
    TaskDetailsDto,
    TaskSummaryDto,
)

TEXT_LIMIT = 2000
TRUNCATION_NOTE = "… (текст обрезан)"


def shorten(text: str | None, limit: int = TEXT_LIMIT) -> str | None:
    """Обрезает длинный текст и честно помечает обрезку.

    Args:
        text: Исходный текст или ``None``.
        limit: Предельная длина.

    Returns:
        Текст в пределах лимита либо ``None``.
    """
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}{TRUNCATION_NOTE}"


def project_summary(project: ProjectSummaryDto) -> dict:
    """Возвращает краткую карточку проекта для списка."""
    return {
        "project_key": project.project_key,
        "name": project.name,
        "status": project.status,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "due_date": project.due_date.isoformat() if project.due_date else None,
    }


def project_detail(overview: ProjectOverviewDto) -> dict:
    """Возвращает подробную карточку проекта со стадиями."""
    return {
        **project_summary(overview.summary),
        "description": shorten(overview.description),
        "total_tasks": overview.total_tasks,
        "stages": [
            {
                "name": stage.name,
                "is_done_stage": stage.is_done_stage,
                "task_count": stage.task_count,
            }
            for stage in overview.stages
        ],
    }


def task_summary(task: TaskSummaryDto) -> dict:
    """Возвращает краткую карточку задачи для списка."""
    return {
        "task_key": task.task_key,
        "checklist": task.checklist,
        "title": task.title,
        "stage": task.stage,
        "is_done": task.is_done,
        "priority": task.priority,
        "assignee": task.assignee,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


def task_detail(details: TaskDetailsDto) -> dict:
    """Возвращает подробную карточку задачи."""
    return {
        **task_summary(details.summary),
        "role": details.role,
        "wbs_path": details.wbs_path,
        "description": shorten(details.description),
        "comment_count": details.comment_count,
    }


def comment_item(comment: CommentDto) -> dict:
    """Возвращает комментарий задачи."""
    return {
        "task_key": comment.task_key,
        "author": comment.author,
        "created_at": comment.created_at.isoformat(),
        "body": shorten(comment.body),
    }
