from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.db.models.kanban import TaskActivityEventType


class StageSchema(BaseModel):
    """Колонка канбан-доски."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    order_index: int
    color: str
    is_done_stage: bool


class StageCreateSchema(BaseModel):
    """Создание колонки канбан-доски."""

    name: str = Field(max_length=100)
    order_index: int = 0
    color: str = Field(max_length=20)
    is_done_stage: bool = False


class StageUpdateSchema(BaseModel):
    """Обновление колонки канбан-доски."""

    name: Optional[str] = Field(default=None, max_length=100)
    order_index: Optional[int] = None
    color: Optional[str] = Field(default=None, max_length=20)
    is_done_stage: Optional[bool] = None


class TaskSchema(BaseModel):
    """Карточка канбан-доски."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    wbs_item_id: Optional[int]
    stage_id: int
    title: str
    description_md: Optional[str]
    due_date: Optional[date]
    position: float
    created_at: datetime
    updated_at: datetime
    wbs_code: Optional[str] = None
    wbs_phase_name: Optional[str] = None
    comments_count: int = 0
    last_comment: Optional[str] = None


class TaskCreateSchema(BaseModel):
    """Создание карточки вручную (всегда без привязки к ИСР)."""

    title: str = Field(max_length=512)
    description_md: Optional[str] = None
    due_date: Optional[date] = None
    stage_id: Optional[int] = None


class TaskUpdateSchema(BaseModel):
    """Обновление полей карточки."""

    title: Optional[str] = Field(default=None, max_length=512)
    description_md: Optional[str] = None
    due_date: Optional[date] = None


class TaskMoveSchema(BaseModel):
    """Перемещение карточки между колонками/позициями."""

    stage_id: int
    position: float


class CommentSchema(BaseModel):
    """Комментарий к задаче."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    author_name: Optional[str]
    body_md: str
    created_at: datetime


class CommentCreateSchema(BaseModel):
    """Создание комментария."""

    author_name: Optional[str] = Field(default=None, max_length=255)
    body_md: str


class ActivitySchema(BaseModel):
    """Запись истории изменений задачи."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    event_type: TaskActivityEventType
    from_value: Optional[str]
    to_value: Optional[str]
    created_at: datetime
