from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentSchema(BaseModel):
    """Комментарий задачи канбана."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор комментария.", examples=[5])
    task_id: int = Field(..., description="Идентификатор задачи.", examples=[3])
    author_name: str | None = Field(
        None,
        description="Свободная подпись автора.",
        examples=["Борис"],
    )
    body_md: str = Field(
        ...,
        description="Текст комментария в Markdown.",
        examples=["Готово к проверке."],
    )
    created_at: datetime = Field(
        ...,
        description="Дата создания комментария.",
        examples=["2026-08-02T12:00:00Z"],
    )


class CommentCreateSchema(BaseModel):
    """Тело запроса для создания комментария."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"author_name": "Борис", "body_md": "Готово к проверке."}}
    )

    author_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Необязательная подпись автора.",
        examples=["Борис"],
    )
    body_md: str = Field(
        ...,
        min_length=1,
        description="Текст комментария в Markdown.",
        examples=["Готово к проверке."],
    )
