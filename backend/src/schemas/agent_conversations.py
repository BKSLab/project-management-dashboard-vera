from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.agent_files import AgentFileSchema
from src.schemas.agent_tools import AgentToolRunSchema
from src.schemas.knowledge import KnowledgeSourceSchema


class AgentConversationSchema(BaseModel):
    """Метаданные доступного диалога без внутренней памяти модели."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="ID диалога.")
    project_id: int = Field(description="Проект, к которому привязан диалог.")
    title: str = Field(description="Название по первому вопросу участника.")
    created_at: datetime = Field(description="Время создания диалога.")
    updated_at: datetime = Field(description="Время последнего изменения диалога.")


class AgentConversationListSchema(BaseModel):
    """Страница личных диалогов в проекте."""

    items: list[AgentConversationSchema] = Field(description="Диалоги от недавних к старым.")
    next_offset: int | None = Field(description="Смещение следующей страницы; null в конце списка.")


class AgentMessageCreateSchema(BaseModel):
    """Новый вопрос: историю и автора определяет сервер."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(
        description="Стабильный UUID отправки; повтор не создаёт новый вопрос."
    )
    content: str = Field(
        min_length=2, max_length=2000, description="Вопрос или продолжение обсуждения."
    )
    file_ids: list[UUID] = Field(
        default_factory=list,
        max_length=5,
        description="До пяти собственных загрузок этого диалога.",
    )

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        """Убирает внешние пробелы и запрещает пустой вопрос или нулевой байт."""
        normalized = value.strip()
        if len(normalized) < 2 or "\x00" in normalized:
            raise ValueError("Введите вопрос длиной от двух символов без нулевых байтов.")
        return normalized


class AgentMessageSchema(BaseModel):
    """Сохранённая реплика и наблюдаемое состояние ответа."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="ID сохранённой реплики.")
    conversation_id: int = Field(description="Диалог реплики.")
    request_id: UUID = Field(description="Общий ключ отправки для вопроса и ответа.")
    role: Literal["user", "assistant"] = Field(description="Автор: участник или агент.")
    content: str = Field(description="Текст вопроса или готового ответа.")
    sources: list[KnowledgeSourceSchema] = Field(description="Проверенные источники ответа.")
    actions: list[AgentToolRunSchema] = Field(
        default_factory=list,
        description="Сохранённые действия и запросы подтверждения этого ответа.",
    )
    files: list[AgentFileSchema] = Field(
        default_factory=list, description="Файлы, выбранные участником для этой реплики."
    )
    status: Literal["queued", "processing", "completed", "failed"] = Field(
        description="Состояние подготовки ответа; вопросы всегда completed."
    )
    error: str | None = Field(description="Безопасное описание неудачной попытки.")
    created_at: datetime = Field(description="Время отправки реплики.")


class AgentMessagePageSchema(BaseModel):
    """Реплики в хронологическом порядке с продолжением к ранним сообщениям."""

    items: list[AgentMessageSchema] = Field(description="Реплики от ранних к поздним.")
    next_before_id: int | None = Field(description="Курсор ранних реплик; null в начале истории.")


class AgentMessageAcceptedSchema(BaseModel):
    """Сохранённый вопрос и поставленный в очередь ответ."""

    user_message: AgentMessageSchema = Field(description="Сохранённый вопрос участника.")
    assistant_message: AgentMessageSchema = Field(description="Состояние связанного ответа.")
