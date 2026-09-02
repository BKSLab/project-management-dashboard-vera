"""Компактное представление сущностей трекера для MCP-инструментов.

Наружу отдаются отображаемые ключи (``PROJ-142``), а не числовые
идентификаторы: агент оперирует тем же, что видит человек в интерфейсе.
Длинные тексты обрезаются с явной пометкой, иначе один вызов инструмента
способен занять весь контекст вызывающей модели.
"""

from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.task_comments import TaskComment
from src.db.models.tasks import Task
from src.services.tasks import build_task_key

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


def project_summary(project: Project) -> dict:
    """Возвращает краткую карточку проекта для списка."""
    return {
        "project_key": project.key,
        "name": project.name,
        "status": project.status.value,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "due_date": project.due_date.isoformat() if project.due_date else None,
    }


def project_detail(
    project: Project,
    *,
    stages: list[ProjectStage],
    task_counts: dict[int, int],
    total_tasks: int,
) -> dict:
    """Возвращает подробную карточку проекта со стадиями."""
    return {
        **project_summary(project),
        "description": shorten(project.description_md),
        "total_tasks": total_tasks,
        "stages": [
            {
                "name": stage.name,
                "is_done_stage": stage.is_done_stage,
                "task_count": task_counts.get(stage.id, 0),
            }
            for stage in stages
        ],
    }


def task_summary(task: Task, *, project: Project, stage: ProjectStage | None) -> dict:
    """Возвращает краткую карточку задачи для списка."""
    return {
        "task_key": build_task_key(project.key, task.number),
        "title": task.title,
        "stage": stage.name if stage else None,
        "is_done": bool(stage and stage.is_done_stage),
        "priority": task.priority.value,
        "assignee": task.assignee,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


def task_detail(
    task: Task,
    *,
    project: Project,
    stage: ProjectStage | None,
    wbs_path: str | None = None,
    comment_count: int = 0,
) -> dict:
    """Возвращает подробную карточку задачи."""
    return {
        **task_summary(task, project=project, stage=stage),
        "role": task.role.value if task.role else None,
        "wbs_path": wbs_path,
        "description": shorten(task.description_md),
        "comment_count": comment_count,
    }


def comment_item(comment: TaskComment, *, task_key: str) -> dict:
    """Возвращает комментарий задачи."""
    return {
        "task_key": task_key,
        "author": comment.author_name,
        "created_at": comment.created_at.isoformat(),
        "body": shorten(comment.body_md),
    }
