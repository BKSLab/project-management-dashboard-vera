"""Представление источников агента: только разрешённые поля текущего каталога."""

from src.knowledge.catalog import ProjectCatalog, ProjectSource, SourceType
from src.schemas.knowledge import KnowledgeSourceCardSchema


def source_card(source: ProjectSource, catalog: ProjectCatalog) -> KnowledgeSourceCardSchema:
    """Собирает карточку из того же PostgreSQL-среза, которым проверены ссылки."""
    data = source.properties
    project = catalog.sources.get(f"project:{source.project_id}")
    key = None
    status = data.get("status")
    assignee = data.get("assignee")
    if source.kind is SourceType.TASK:
        if project and data.get("number") is not None:
            key = f"{project.properties.get('key', '')}-{data['number']}"
        stage = catalog.sources.get(f"stage:{data.get('stage_id')}")
        status = stage.title if stage else None
        user_ids = {
            row["user_id"]
            for row in catalog.rows.get("task_participants", [])
            if row.get("task_id") == source.entity_id and row.get("role") == "EXECUTOR"
        }
        names = [
            " ".join(user.get(part) or "" for part in ("last_name", "first_name")).strip()
            or user.get("username", "")
            for user in catalog.rows.get("users", [])
            if user["id"] in user_ids
        ]
        assignee = ", ".join(names) or assignee
    elif source.kind is SourceType.RISK:
        key = f"RISK-{source.entity_id}"
    elif source.kind is SourceType.PROJECT:
        key = data.get("key")
    return KnowledgeSourceCardSchema(
        key=key,
        status=status,
        priority=data.get("priority"),
        assignee=assignee,
        due_date=str(data["due_date"]) if data.get("due_date") else None,
        summary=(data.get("description_md") or "")[:240] or None,
    )
