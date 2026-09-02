from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.db.models.projects import ProjectStatus

KEY_PATTERN = r"^[A-Za-z][A-Za-z0-9]{1,9}$"
COLOR_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class ProjectSchema(BaseModel):
    """Проект трекера."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор проекта.", examples=[1])
    key: str = Field(..., description="Короткий код проекта.", examples=["PROJ"])
    name: str = Field(..., description="Название проекта.", examples=["Агент Вера"])
    description_md: str | None = Field(
        None,
        description="Описание проекта в Markdown.",
        examples=["Персональный ассистент для подбора работы."],
    )
    status: ProjectStatus = Field(..., description="Статус проекта.", examples=["ACTIVE"])
    color: str = Field(..., description="HEX-цвет проекта.", examples=["#58a6ff"])
    icon: str | None = Field(None, description="Эмодзи-иконка проекта.", examples=["🚀"])
    start_date: date | None = Field(
        None,
        description="Плановая дата начала.",
        examples=["2026-09-01"],
    )
    due_date: date | None = Field(
        None,
        description="Плановая дата завершения.",
        examples=["2026-12-20"],
    )
    order_index: int = Field(..., description="Порядок проекта в списке.", examples=[0])
    created_at: datetime = Field(
        ...,
        description="Дата создания проекта.",
        examples=["2026-09-01T10:00:00Z"],
    )
    updated_at: datetime = Field(
        ...,
        description="Дата последнего обновления проекта.",
        examples=["2026-09-02T12:00:00Z"],
    )


class ProjectCreateSchema(BaseModel):
    """Тело запроса для создания проекта."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "PROJ",
                "name": "Агент Вера",
                "description_md": "Персональный ассистент для подбора работы.",
                "color": "#58a6ff",
                "icon": "🚀",
            }
        }
    )

    key: str = Field(
        ...,
        pattern=KEY_PATTERN,
        description="Короткий код проекта: латиница и цифры, от 2 до 10 символов.",
        examples=["PROJ"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Название проекта.",
        examples=["Агент Вера"],
    )
    description_md: str | None = Field(
        None,
        description="Описание проекта в Markdown.",
        examples=["Персональный ассистент для подбора работы."],
    )
    status: ProjectStatus = Field(
        ProjectStatus.PLANNING,
        description="Начальный статус проекта.",
        examples=["PLANNING"],
    )
    color: str = Field(
        "#58a6ff",
        pattern=COLOR_PATTERN,
        description="HEX-цвет проекта.",
        examples=["#58a6ff"],
    )
    icon: str | None = Field(
        None,
        max_length=8,
        description="Эмодзи-иконка проекта.",
        examples=["🚀"],
    )
    start_date: date | None = Field(
        None,
        description="Плановая дата начала.",
        examples=["2026-09-01"],
    )
    due_date: date | None = Field(
        None,
        description="Плановая дата завершения.",
        examples=["2026-12-20"],
    )

    @field_validator("key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        """Приводит код проекта к верхнему регистру."""
        return value.upper()


class ProjectUpdateSchema(BaseModel):
    """Тело запроса для частичного обновления проекта."""

    model_config = ConfigDict(json_schema_extra={"example": {"status": "ACTIVE"}})

    key: str | None = Field(
        None,
        pattern=KEY_PATTERN,
        description="Новый короткий код проекта.",
        examples=["PROJ"],
    )
    name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Новое название проекта.",
        examples=["Агент Вера 2.0"],
    )
    description_md: str | None = Field(
        None,
        description="Новое описание в Markdown.",
        examples=["Обновлённое описание проекта."],
    )
    status: ProjectStatus | None = Field(
        None,
        description="Новый статус проекта.",
        examples=["ACTIVE"],
    )
    color: str | None = Field(
        None,
        pattern=COLOR_PATTERN,
        description="Новый HEX-цвет проекта.",
        examples=["#a371f7"],
    )
    icon: str | None = Field(
        None,
        max_length=8,
        description="Новая эмодзи-иконка проекта.",
        examples=["🛠"],
    )
    start_date: date | None = Field(
        None,
        description="Новая дата начала или null для очистки.",
        examples=["2026-09-01"],
    )
    due_date: date | None = Field(
        None,
        description="Новая дата завершения или null для очистки.",
        examples=["2026-12-20"],
    )
    order_index: int | None = Field(
        None,
        ge=0,
        description="Новый порядок проекта в списке.",
        examples=[2],
    )

    @field_validator("key")
    @classmethod
    def normalize_key(cls, value: str | None) -> str | None:
        """Приводит код проекта к верхнему регистру."""
        return value.upper() if value is not None else None


class StageBreakdownSchema(BaseModel):
    """Количество задач в одной стадии проекта."""

    stage_id: int = Field(..., description="Идентификатор стадии.", examples=[3])
    stage_name: str = Field(..., description="Название стадии.", examples=["В работе"])
    color: str = Field(..., description="HEX-цвет стадии.", examples=["#58a6ff"])
    is_done_stage: bool = Field(..., description="Признак завершающей стадии.", examples=[False])
    tasks_count: int = Field(..., ge=0, description="Количество задач в стадии.", examples=[4])


class ProjectStatsSchema(BaseModel):
    """Показатели проекта для карточки и обзорного экрана."""

    project_id: int = Field(..., description="Идентификатор проекта.", examples=[1])
    total_tasks: int = Field(..., ge=0, description="Всего задач в проекте.", examples=[18])
    done_tasks: int = Field(..., ge=0, description="Задач в завершающих стадиях.", examples=[9])
    in_progress_tasks: int = Field(
        ...,
        ge=0,
        description="Задач в работе: не в первой и не в завершающей стадии.",
        examples=[5],
    )
    overdue_tasks: int = Field(
        ...,
        ge=0,
        description="Незавершённых задач с истёкшим сроком.",
        examples=[2],
    )
    due_soon_tasks: int = Field(
        ...,
        ge=0,
        description="Незавершённых задач со сроком в ближайшие 7 дней.",
        examples=[3],
    )
    unassigned_tasks: int = Field(
        ...,
        ge=0,
        description="Задач, не распределённых по разделам ИСР.",
        examples=[6],
    )
    completion_rate: float = Field(
        ...,
        ge=0,
        le=1,
        description="Доля выполненных задач от общего числа.",
        examples=[0.5],
    )
    next_due_date: date | None = Field(
        None,
        description="Ближайший срок среди незавершённых задач.",
        examples=["2026-09-08"],
    )
    stage_breakdown: list[StageBreakdownSchema] = Field(
        default_factory=list,
        description="Распределение задач по стадиям проекта.",
    )
