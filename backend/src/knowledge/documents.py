from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from src.db.models.documents import Document
from src.db.models.projects import Project
from src.db.models.task_attachments import TaskAttachment
from src.db.models.task_comments import TaskComment
from src.db.models.tasks import Task
from src.db.models.wbs_nodes import WbsNode
from src.knowledge.chunking import chunk_markdown, chunk_text
from src.services.tasks import build_task_key

POINT_NAMESPACE = "project-management-dashboard-vera:knowledge"


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Текст и payload одного детерминированного Qdrant point."""

    point_id: str
    text: str
    payload: dict


def build_wbs_paths(nodes: list[WbsNode]) -> dict[int, str]:
    """Вычисляет человекочитаемый путь каждого узла ИСР."""
    by_id = {node.id: node for node in nodes}
    paths: dict[int, str] = {}
    for node in nodes:
        titles: list[str] = []
        current: WbsNode | None = node
        visited: set[int] = set()
        while current is not None and current.id not in visited:
            visited.add(current.id)
            titles.append(current.title)
            current = by_id.get(current.parent_id) if current.parent_id is not None else None
        paths[node.id] = " / ".join(reversed(titles))
    return paths


def build_project_document(project: Project) -> KnowledgeDocument:
    """Строит семантический паспорт проекта."""
    text = "\n".join(
        part
        for part in (
            "Тип: проект",
            f"Код: {project.key}",
            f"Название: {project.name}",
            f"Описание:\n{project.description_md}" if project.description_md else None,
        )
        if part
    )
    return _document(
        project_id=project.id,
        entity_type="project",
        entity_id=project.id,
        chunk_index=0,
        text=text,
        title=f"{project.key} · {project.name}",
        updated_at=project.updated_at.isoformat(),
    )


def build_task_document(
    task: Task,
    *,
    project: Project,
    wbs_path: str | None,
) -> KnowledgeDocument:
    """Строит семантический паспорт только из устойчивых смысловых полей задачи."""
    task_key = build_task_key(project.key, task.number)
    text = "\n".join(
        part
        for part in (
            "Тип: задача",
            f"Ключ: {task_key}",
            f"Название: {task.title}",
            f"Раздел ИСР: {wbs_path}" if wbs_path else "Раздел ИСР: не распределена",
            f"Описание:\n{task.description_md}" if task.description_md else None,
        )
        if part
    )
    return _document(
        project_id=project.id,
        entity_type="task",
        entity_id=task.id,
        chunk_index=0,
        text=text,
        title=f"{task_key} · {task.title}",
        task_id=task.id,
        updated_at=task.updated_at.isoformat(),
        extra={
            "task_key": task_key,
            "wbs_path": wbs_path,
        },
    )


def build_comment_document(
    comment: TaskComment,
    *,
    task: Task,
    project: Project,
) -> KnowledgeDocument:
    """Строит отдельный semantic object комментария."""
    task_key = build_task_key(project.key, task.number)
    text = "\n".join(
        (
            "Тип: комментарий к задаче",
            f"Задача: {task_key}",
            f"Автор: {comment.author_name or 'не указан'}",
            f"Комментарий:\n{comment.body_md}",
        )
    )
    return _document(
        project_id=project.id,
        entity_type="comment",
        entity_id=comment.id,
        chunk_index=0,
        text=text,
        title=f"Комментарий · {task_key}",
        task_id=task.id,
        updated_at=comment.created_at.isoformat(),
        extra={"task_key": task_key, "author_name": comment.author_name},
    )


def build_document_chunks(
    document: Document,
    *,
    target_chars: int,
    overlap_chars: int,
) -> list[KnowledgeDocument]:
    """Разбивает Markdown-документ по заголовкам и логическим блокам."""
    chunks = chunk_markdown(
        document.content_md,
        target_chars=target_chars,
        overlap_chars=overlap_chars,
    )
    return [
        _document(
            project_id=document.project_id,
            entity_type="document",
            entity_id=document.id,
            chunk_index=chunk.index,
            text="\n".join(
                part
                for part in (
                    "Тип: документ проекта",
                    f"Документ: {document.title}",
                    f"Раздел: {chunk.heading}" if chunk.heading else None,
                    f"Содержимое:\n{chunk.text}",
                )
                if part
            ),
            title=document.title,
            updated_at=document.updated_at.isoformat(),
            extra={
                "document_id": str(document.id),
                "document_slug": document.slug,
                "heading": chunk.heading,
            },
        )
        for chunk in chunks
    ]


def build_attachment_chunks(
    attachment: TaskAttachment,
    *,
    extracted_text: str,
    task: Task,
    project: Project,
    target_chars: int,
    overlap_chars: int,
) -> list[KnowledgeDocument]:
    """Строит chunks извлечённого PDF/DOCX/TXT/Markdown-вложения."""
    task_key = build_task_key(project.key, task.number)
    chunks = chunk_text(
        extracted_text,
        target_chars=target_chars,
        overlap_chars=overlap_chars,
    )
    return [
        _document(
            project_id=project.id,
            entity_type="attachment",
            entity_id=attachment.id,
            chunk_index=index,
            text=(
                "Тип: вложение задачи\n"
                f"Задача: {task_key}\n"
                f"Файл: {attachment.original_name}\n"
                f"Содержимое:\n{chunk}"
            ),
            title=f"{attachment.original_name} · {task_key}",
            task_id=task.id,
            updated_at=attachment.created_at.isoformat(),
            extra={
                "attachment_id": str(attachment.id),
                "task_key": task_key,
            },
        )
        for index, chunk in enumerate(chunks)
    ]


def _document(
    *,
    project_id: int,
    entity_type: str,
    entity_id: int,
    chunk_index: int,
    text: str,
    title: str,
    updated_at: str,
    task_id: int | None = None,
    extra: dict | None = None,
) -> KnowledgeDocument:
    source_id = f"{entity_type}:{entity_id}"
    payload = {
        "project_id": str(project_id),
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "source_id": source_id,
        "task_id": str(task_id) if task_id is not None else None,
        "title": title,
        "text": text,
        "chunk_index": chunk_index,
        "updated_at": updated_at,
        **(extra or {}),
    }
    return KnowledgeDocument(
        point_id=str(
            uuid5(
                NAMESPACE_URL,
                f"{POINT_NAMESPACE}:{project_id}:{entity_type}:{entity_id}:{chunk_index}",
            )
        ),
        text=text,
        payload=payload,
    )
