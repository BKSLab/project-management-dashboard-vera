from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.db.models.task_activity import TaskActivityEventType


class ActivitySchema(BaseModel):
    """Неизменяемое событие истории задачи."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор события.", examples=[7])
    task_id: int = Field(..., description="Идентификатор задачи.", examples=[3])
    event_type: TaskActivityEventType = Field(
        ...,
        description="Тип изменения задачи.",
        examples=["STAGE_CHANGED"],
    )
    from_value: str | None = Field(
        None,
        description="Предыдущее значение.",
        examples=["Бэклог"],
    )
    to_value: str | None = Field(
        None,
        description="Новое значение.",
        examples=["В работе"],
    )
    created_at: datetime = Field(
        ...,
        description="Дата фиксации события.",
        examples=["2026-08-02T12:00:00Z"],
    )
