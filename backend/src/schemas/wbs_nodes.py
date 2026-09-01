from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.tasks import TaskCompactSchema


class WbsNodeSchema(BaseModel):
    """Структурный узел ИСР.

    Номер узла (``1.2.1``) в ответе не передаётся: он вычисляется на клиенте
    из ``parent_id`` и ``position``, поэтому не может разойтись со структурой.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор узла.", examples=[32])
    project_id: int = Field(..., description="Идентификатор проекта.", examples=[1])
    parent_id: int | None = Field(
        None,
        description="Родительский узел; null для верхнего уровня.",
        examples=[12],
    )
    title: str = Field(..., description="Название раздела.", examples=["Backend"])
    position: float = Field(
        ...,
        description="Позиция среди узлов одного уровня.",
        examples=[2000.0],
    )
    created_at: datetime = Field(
        ...,
        description="Дата создания узла.",
        examples=["2026-09-01T10:00:00Z"],
    )
    updated_at: datetime = Field(
        ...,
        description="Дата последнего обновления узла.",
        examples=["2026-09-02T12:00:00Z"],
    )


class WbsStatsSchema(BaseModel):
    """Сводка по структуре проекта."""

    total_nodes: int = Field(..., ge=0, description="Всего разделов ИСР.", examples=[7])
    total_tasks: int = Field(..., ge=0, description="Всего задач в проекте.", examples=[38])
    assigned_tasks: int = Field(
        ...,
        ge=0,
        description="Задач, распределённых по разделам.",
        examples=[20],
    )
    unassigned_tasks: int = Field(
        ...,
        ge=0,
        description="Задач в пуле нераспределённых.",
        examples=[18],
    )
    done_tasks: int = Field(..., ge=0, description="Задач в завершающих стадиях.", examples=[24])
    overdue_tasks: int = Field(
        ...,
        ge=0,
        description="Незавершённых задач с истёкшим сроком.",
        examples=[2],
    )


class WbsStructureSchema(BaseModel):
    """Полная структура ИСР проекта, получаемая одним запросом."""

    nodes: list[WbsNodeSchema] = Field(
        default_factory=list,
        description="Плоский список узлов; дерево собирает клиент.",
    )
    tasks: list[TaskCompactSchema] = Field(
        default_factory=list,
        description="Компактные задачи проекта, включая нераспределённые.",
    )
    stats: WbsStatsSchema = Field(..., description="Сводка по структуре проекта.")


class WbsNodeCreateSchema(BaseModel):
    """Тело запроса для создания раздела ИСР."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "Backend", "parent_id": None}}
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Название раздела.",
        examples=["Backend"],
    )
    parent_id: int | None = Field(
        None,
        gt=0,
        description="Родительский раздел; null создаёт раздел верхнего уровня.",
        examples=[12],
    )


class WbsNodeUpdateSchema(BaseModel):
    """Тело запроса для переименования раздела ИСР."""

    model_config = ConfigDict(json_schema_extra={"example": {"title": "Backend API"}})

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Новое название раздела.",
        examples=["Backend API"],
    )


class WbsNodeMoveSchema(BaseModel):
    """Тело запроса для перемещения раздела в структуре.

    Позицию внутри уровня вычисляет backend: клиент указывает только целевого
    родителя и соседа, перед которым нужно встать.
    """

    model_config = ConfigDict(json_schema_extra={"example": {"parent_id": 12, "before_id": 33}})

    parent_id: int | None = Field(
        None,
        gt=0,
        description="Новый родитель; null переносит раздел на верхний уровень.",
        examples=[12],
    )
    before_id: int | None = Field(
        None,
        gt=0,
        description="Раздел, перед которым встаёт перемещаемый; null — в конец уровня.",
        examples=[33],
    )


class WbsTaskAssignSchema(BaseModel):
    """Тело запроса для назначения задачи в раздел ИСР."""

    model_config = ConfigDict(json_schema_extra={"example": {"wbs_node_id": 32}})

    wbs_node_id: int = Field(..., gt=0, description="Целевой раздел ИСР.", examples=[32])


class WbsNodeDeleteResultSchema(BaseModel):
    """Результат удаления раздела ИСР."""

    deleted_nodes: int = Field(
        ...,
        ge=1,
        description="Количество удалённых разделов вместе с подразделами.",
        examples=[4],
    )
    released_tasks: int = Field(
        ...,
        ge=0,
        description="Количество задач, возвращённых в пул нераспределённых.",
        examples=[8],
    )
