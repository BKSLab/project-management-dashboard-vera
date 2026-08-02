from pydantic import BaseModel, ConfigDict, Field


class StageSchema(BaseModel):
    """Стадия канбан-доски."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор стадии.", examples=[1])
    name: str = Field(..., description="Название стадии.", examples=["В работе"])
    order_index: int = Field(..., description="Порядок отображения стадии.", examples=[2])
    color: str = Field(..., description="HEX-цвет стадии.", examples=["#F5B800"])
    is_done_stage: bool = Field(
        ...,
        description="Признак завершающей стадии.",
        examples=[False],
    )


class StageCreateSchema(BaseModel):
    """Тело запроса для создания стадии канбана."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "В работе",
                "order_index": 2,
                "color": "#F5B800",
                "is_done_stage": False,
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Название стадии.",
        examples=["В работе"],
    )
    order_index: int = Field(
        0,
        ge=0,
        description="Порядок отображения стадии.",
        examples=[2],
    )
    color: str = Field(
        ...,
        min_length=4,
        max_length=20,
        description="Цвет стадии.",
        examples=["#F5B800"],
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
        description="Новое название.",
        examples=["На проверке"],
    )
    order_index: int | None = Field(
        None,
        ge=0,
        description="Новый порядок отображения.",
        examples=[3],
    )
    color: str | None = Field(
        None,
        min_length=4,
        max_length=20,
        description="Новый цвет.",
        examples=["#A855F7"],
    )
    is_done_stage: bool | None = Field(
        None,
        description="Новый завершающий признак.",
        examples=[False],
    )
