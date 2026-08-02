from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from src.db.models.wbs import WbsRole


class WbsProgressSchema(BaseModel):
    """Rollup-прогресс по листовым задачам узла ИСР."""

    done: int = Field(
        ...,
        ge=0,
        description="Количество завершённых листовых задач.",
        examples=[8],
    )
    total: int = Field(
        ...,
        ge=0,
        description="Общее количество листовых задач.",
        examples=[12],
    )


class WbsTaskRefSchema(BaseModel):
    """Краткая ссылка на задачу листового узла ИСР."""

    id: int = Field(..., description="Идентификатор задачи канбана.", examples=[3])
    stage_id: int = Field(..., description="Идентификатор текущей стадии.", examples=[2])
    stage_name: str = Field(..., description="Название текущей стадии.", examples=["В работе"])
    due_date: date | None = Field(
        None,
        description="Плановая дата завершения задачи.",
        examples=["2026-08-10"],
    )


class WbsNodeSchema(BaseModel):
    """Рекурсивный узел дерева ИСР с прогрессом или задачей."""

    id: int = Field(..., description="Уникальный идентификатор узла.", examples=[12])
    code: str = Field(..., description="Иерархический код узла ИСР.", examples=["1.1.3"])
    phase_name: str | None = Field(
        None,
        description="Название корневой фазы.",
        examples=["Проектирование"],
    )
    title: str = Field(..., description="Название работы.", examples=["Подготовить отчёт"])
    role: WbsRole | None = Field(None, description="Ответственная роль.", examples=["PM"])
    progress: WbsProgressSchema | None = Field(
        None,
        description="Rollup-прогресс нелистового узла.",
        examples=[{"done": 8, "total": 12}],
    )
    task: WbsTaskRefSchema | None = Field(
        None,
        description="Связанная задача листового узла.",
        examples=[{"id": 3, "stage_id": 2, "stage_name": "В работе", "due_date": None}],
    )
    children: list["WbsNodeSchema"] = Field(
        default_factory=list,
        description="Дочерние узлы ИСР.",
        examples=[[]],
    )


class WbsItemSchema(BaseModel):
    """Плоское представление узла ИСР."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор узла.", examples=[12])
    parent_id: int | None = Field(
        None,
        description="Идентификатор родительского узла.",
        examples=[10],
    )
    code: str = Field(..., description="Иерархический код ИСР.", examples=["1.1.3"])
    phase_name: str | None = Field(
        None,
        description="Название корневой фазы.",
        examples=["Проектирование"],
    )
    title: str = Field(..., description="Название работы.", examples=["Подготовить отчёт"])
    role: WbsRole | None = Field(None, description="Ответственная роль.", examples=["PM"])
    order_index: int = Field(
        ...,
        ge=0,
        description="Порядок среди соседних узлов.",
        examples=[2],
    )
    is_leaf: bool = Field(
        ...,
        description="Признак листового узла со связанной задачей.",
        examples=[True],
    )


class WbsItemCreateSchema(BaseModel):
    """Тело запроса для создания узла ИСР."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "parent_id": 12,
                "title": "Подготовить отчёт",
                "role": "PM",
                "phase_name": None,
            }
        }
    )

    parent_id: int | None = Field(
        None,
        gt=0,
        description="Родитель или null для корня.",
        examples=[12],
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Название работы.",
        examples=["Подготовить отчёт"],
    )
    role: WbsRole | None = Field(None, description="Ответственная роль.", examples=["PM"])
    phase_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Название фазы для нового корневого узла.",
        examples=["Проектирование"],
    )


class WbsItemUpdateSchema(BaseModel):
    """Тело запроса для частичного обновления узла ИСР."""

    model_config = ConfigDict(json_schema_extra={"example": {"title": "Актуальная работа"}})

    title: str | None = Field(
        None,
        min_length=1,
        max_length=512,
        description="Новое название.",
        examples=["Актуальная работа"],
    )
    role: WbsRole | None = Field(
        None,
        description="Новая ответственная роль.",
        examples=["QA"],
    )
    phase_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Новое название корневой фазы.",
        examples=["Реализация"],
    )
