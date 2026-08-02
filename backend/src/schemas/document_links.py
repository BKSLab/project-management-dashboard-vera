from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentLinkSchema(BaseModel):
    """Связь документа с задачей канбана или узлом ИСР."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор связи.", examples=[1])
    document_id: int = Field(..., description="Идентификатор документа.", examples=[1])
    kanban_task_id: int | None = Field(
        None,
        description="Идентификатор связанной задачи канбана.",
        examples=[3],
    )
    wbs_item_id: int | None = Field(
        None,
        description="Идентификатор связанного узла ИСР.",
        examples=[12],
    )


class DocumentLinkCreateSchema(BaseModel):
    """Тело запроса для создания связи документа."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"document_id": 1, "kanban_task_id": 3, "wbs_item_id": None}}
    )

    document_id: int = Field(..., gt=0, description="Идентификатор документа.", examples=[1])
    kanban_task_id: int | None = Field(
        None,
        gt=0,
        description="Идентификатор задачи; взаимоисключается с wbs_item_id.",
        examples=[3],
    )
    wbs_item_id: int | None = Field(
        None,
        gt=0,
        description="Идентификатор узла ИСР; взаимоисключается с kanban_task_id.",
        examples=[12],
    )

    @model_validator(mode="after")
    def check_exactly_one_target(self) -> Self:
        """Проверяет, что указан ровно один целевой объект."""
        if (self.kanban_task_id is None) == (self.wbs_item_id is None):
            raise ValueError(
                "Должно быть заполнено ровно одно из полей: kanban_task_id или wbs_item_id."
            )
        return self


class LinkedTargetSchema(BaseModel):
    """Задача или узел ИСР, связанный с документом."""

    link_id: int = Field(..., description="Идентификатор связи.", examples=[1])
    kanban_task_id: int | None = Field(
        None,
        description="Идентификатор задачи канбана.",
        examples=[3],
    )
    wbs_item_id: int | None = Field(
        None,
        description="Идентификатор узла ИСР.",
        examples=[12],
    )
    title: str = Field(
        ...,
        description="Человекочитаемое название целевого объекта.",
        examples=["1.1.3 Подготовить отчёт"],
    )


class LinkedDocumentSchema(BaseModel):
    """Документ, связанный с задачей канбана или узлом ИСР."""

    link_id: int = Field(..., description="Идентификатор связи.", examples=[1])
    document_id: int = Field(..., description="Идентификатор документа.", examples=[1])
    slug: str = Field(..., description="URL-идентификатор документа.", examples=["project-plan"])
    title: str = Field(..., description="Заголовок документа.", examples=["План проекта"])
