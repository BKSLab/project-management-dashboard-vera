from src.schemas.projects import ProjectDescriptionSchema

DESCRIPTION_BLOCKS = (
    ("problem", "Проблема"),
    ("goal", "Цель"),
    ("expected_result", "Ожидаемый результат"),
    ("additional", "Дополнительно"),
)


def compose_project_description(sections: ProjectDescriptionSchema) -> str | None:
    """Собирает текст для существующих FTS, embeddings, аналитики и Markdown-вида."""
    return (
        "\n\n".join(
            f"## {title}\n\n{getattr(sections, name)}"
            for name, title in DESCRIPTION_BLOCKS
            if getattr(sections, name)
        )
        or None
    )
