from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentToolRunSchema(BaseModel):
    """Проверяемое действие и результат в личном диалоге."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(description="ID действия.")
    tool_name: str = Field(description="Имя инструмента.")
    title: str = Field(description="Название действия.")
    arguments: dict[str, Any] = Field(description="Конкретные параметры действия.")
    status: Literal["pending", "completed", "rejected", "failed"] = Field(
        description="Состояние действия."
    )
    result: dict[str, Any] = Field(description="Сохранённый результат.")
    created_at: datetime = Field(description="Время запроса действия.")


class AgentToolDecisionSchema(BaseModel):
    """Решение участника по конкретным сохранённым параметрам."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"] = Field(description="Выполнить или отклонить действие.")
