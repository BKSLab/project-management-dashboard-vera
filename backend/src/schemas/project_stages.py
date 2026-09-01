from pydantic import BaseModel, ConfigDict, Field

COLOR_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class StageSchema(BaseModel):
    """Стадия канбан-доски проекта."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор стадии.", examples=[2])
    project_id: int = Field(..., description="Идентификатор проекта.", examples=[1])
    name: str = Field(..., description="Название стадии.", examples=["В работе"])
    order_index: int = Field(..., description="Порядок колонки на доске.", examples=[1])
    color: str = Field(..., description="HEX-цвет стадии.", examples=["#58a6ff"])
    is_done_stage: bool = Field(..., description="Признак завершающей стадии.", examples=[False])


class StageCreateSchema(BaseModel):
    """Тело запроса для создания стадии проекта."""

    model_config = ConfigDict(json_schema_extra={"example": {"name": "Ревью", "color": "#a371f7"}})

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Название стадии.",
        examples=["Ревью"],
    )
    color: str = Field(
        "#7d8793",
        pattern=COLOR_PATTERN,
        description="HEX-цвет стадии.",
        examples=["#a371f7"],
    )
    is_done_stage: bool = Field(
        False,
        description="Признак завершающей стадии.",
        examples=[False],
    )


class StageUpdateSchema(BaseModel):
    """Тело запроса для частичного обновления стадии."""

    model_config = ConfigDict(json_schema_extra={"example": {"name": "Проверка"}})

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Новое название стадии.",
        examples=["Проверка"],
    )
    color: str | None = Field(
        None,
        pattern=COLOR_PATTERN,
        description="Новый HEX-цвет стадии.",
        examples=["#d29922"],
    )
    order_index: int | None = Field(
        None,
        ge=0,
        description="Новый порядок колонки на доске.",
        examples=[2],
    )
    is_done_stage: bool | None = Field(
        None,
        description="Новый признак завершающей стадии.",
        examples=[True],
    )
