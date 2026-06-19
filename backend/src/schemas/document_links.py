from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator


class DocumentLinkSchema(BaseModel):
    """Связь документа с задачей канбана или узлом ИСР."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    kanban_task_id: Optional[int]
    wbs_item_id: Optional[int]


class DocumentLinkCreateSchema(BaseModel):
    """Создание связи документа."""

    document_id: int
    kanban_task_id: Optional[int] = None
    wbs_item_id: Optional[int] = None

    @model_validator(mode='after')
    def check_exactly_one_target(self) -> 'DocumentLinkCreateSchema':
        if (self.kanban_task_id is None) == (self.wbs_item_id is None):
            raise ValueError(
                "Должно быть заполнено ровно одно из полей: kanban_task_id или wbs_item_id."
            )
        return self


class LinkedTargetSchema(BaseModel):
    """Связанная с документом задача/узел ИСР (для страницы документа)."""

    link_id: int
    kanban_task_id: Optional[int]
    wbs_item_id: Optional[int]
    title: str


class LinkedDocumentSchema(BaseModel):
    """Связанный с задачей/узлом ИСР документ (для TaskDrawer)."""

    link_id: int
    document_id: int
    slug: str
    title: str
