from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.db.models.wbs import WbsRole


class WbsProgressSchema(BaseModel):
    """Прогресс выполнения по дочерним листовым задачам."""

    done: int
    total: int


class WbsTaskRefSchema(BaseModel):
    """Ссылка на связанную задачу канбана для листового узла ИСР."""

    id: int
    stage_id: int
    stage_name: str
    due_date: Optional[date]


class WbsNodeSchema(BaseModel):
    """Узел дерева ИСР с rollup-прогрессом."""

    id: int
    code: str
    phase_name: Optional[str]
    title: str
    role: Optional[WbsRole]
    progress: Optional[WbsProgressSchema]
    task: Optional[WbsTaskRefSchema]
    children: list['WbsNodeSchema']


class WbsItemSchema(BaseModel):
    """Плоское представление узла ИСР (ответ создания/обновления)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: Optional[int]
    code: str
    phase_name: Optional[str]
    title: str
    role: Optional[WbsRole]
    order_index: int
    is_leaf: bool


class WbsItemCreateSchema(BaseModel):
    """Создание узла ИСР (дочернего или нового узла верхнего уровня)."""

    parent_id: Optional[int] = None
    title: str = Field(max_length=512)
    role: Optional[WbsRole] = None
    phase_name: Optional[str] = Field(default=None, max_length=255)


class WbsItemUpdateSchema(BaseModel):
    """Обновление узла ИСР."""

    title: Optional[str] = Field(default=None, max_length=512)
    role: Optional[WbsRole] = None
    phase_name: Optional[str] = Field(default=None, max_length=255)
