from pydantic import BaseModel, ConfigDict, Field


class DocumentLinkSchema(BaseModel):
    """Связь документа с задачей."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор связи.", examples=[1])
    document_id: int = Field(..., description="Идентификатор документа.", examples=[1])
    task_id: int = Field(..., description="Идентификатор связанной задачи.", examples=[142])


class DocumentLinkCreateSchema(BaseModel):
    """Тело запроса для создания связи документа с задачей."""

    model_config = ConfigDict(json_schema_extra={"example": {"document_id": 1, "task_id": 142}})

    document_id: int = Field(..., gt=0, description="Идентификатор документа.", examples=[1])
    task_id: int = Field(..., gt=0, description="Идентификатор задачи.", examples=[142])


class LinkedTaskSchema(BaseModel):
    """Задача, связанная с документом."""

    link_id: int = Field(..., description="Идентификатор связи.", examples=[1])
    task_id: int = Field(..., description="Идентификатор задачи.", examples=[142])
    key: str = Field(..., description="Отображаемый идентификатор задачи.", examples=["VERA-142"])
    title: str = Field(
        ...,
        description="Заголовок задачи.",
        examples=["Реализовать фильтрацию проектов"],
    )


class LinkedDocumentSchema(BaseModel):
    """Документ, связанный с задачей."""

    link_id: int = Field(..., description="Идентификатор связи.", examples=[1])
    document_id: int = Field(..., description="Идентификатор документа.", examples=[1])
    slug: str = Field(..., description="URL-идентификатор документа.", examples=["project-plan"])
    title: str = Field(..., description="Заголовок документа.", examples=["План проекта"])
