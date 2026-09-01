from typing import Literal

from pydantic import BaseModel, Field, field_validator


class KnowledgeChatMessageSchema(BaseModel):
    """Одна предыдущая реплика для уточняющего вопроса."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        """Не пропускает пустые реплики из одних пробелов."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Реплика не может быть пустой.")
        return normalized


class KnowledgeAskSchema(BaseModel):
    """Вопрос Project Agent с короткой историей текущего диалога."""

    question: str = Field(min_length=2, max_length=2000)
    history: list[KnowledgeChatMessageSchema] = Field(default_factory=list, max_length=10)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        """Нормализует вопрос до передачи embeddings API."""
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Вопрос слишком короткий.")
        return normalized


class KnowledgeSourceSchema(BaseModel):
    """Проверяемый источник ответа и данные для навигации в UI."""

    source_id: str
    entity_type: Literal["project", "task", "document", "comment", "attachment"]
    entity_id: int
    title: str
    excerpt: str | None = None
    score: float | None = None
    task_id: int | None = None
    document_slug: str | None = None


class KnowledgeAnswerSchema(BaseModel):
    """Ответ агента, основанный только на данных доступного проекта."""

    answer: str
    sources: list[KnowledgeSourceSchema]


class KnowledgeStatusSchema(BaseModel):
    """Наблюдаемое состояние индекса проекта без раскрытия collection name."""

    enabled: bool
    ready: bool
    points_count: int | None
    pending_jobs: int
    processing_jobs: int
    failed_jobs: int
    last_error: str | None


class KnowledgeReindexSchema(BaseModel):
    """Подтверждение постановки полной переиндексации в очередь."""

    queued: bool = True
