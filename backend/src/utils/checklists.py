"""Единое представление чек-листов в AI-контексте и поисковом индексе."""

from src.schemas.task_checklists import TaskChecklistSchema


def checklist_context(
    value: dict | TaskChecklistSchema | None, *, limit: int = 100, chars: int = 500
) -> dict | None:
    """Передаёт текст, порядок, отметки и полные счётчики без служебных UUID."""
    if value is None:
        return None
    data = TaskChecklistSchema.model_validate(value)
    return {
        "title": data.title,
        "total_items": len(data.items),
        "completed_items": sum(item.is_completed for item in data.items),
        "included_items": min(len(data.items), limit),
        "items": [
            {
                "text": item.text if len(item.text) <= chars else item.text[:chars] + "…",
                "is_completed": item.is_completed,
            }
            for item in data.items[:limit]
        ],
    }


def checklist_text(value: dict | TaskChecklistSchema | None) -> str:
    """Формирует Markdown с отметками для индекса и текстовых prompt-ов."""
    data = checklist_context(value)
    if data is None:
        return ""
    rows = [f"Чек-лист «{data['title']}»: {data['completed_items']}/{data['total_items']}"]
    rows.extend(
        f"- [{'x' if item['is_completed'] else ' '}] {item['text']}" for item in data["items"]
    )
    return "\n".join(rows)
