from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskSchema(BaseModel):
    """Карточка канбан-доски с агрегированным контекстом."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор задачи.", examples=[3])
    wbs_item_id: int | None = Field(
        None,
        description="Идентификатор связанного узла ИСР.",
        examples=[12],
    )
    stage_id: int = Field(..., description="Идентификатор текущей стадии.", examples=[2])
    title: str = Field(..., description="Заголовок задачи.", examples=["Подготовить отчёт"])
    description_md: str | None = Field(
        None,
        description="Описание задачи в Markdown.",
        examples=["Собрать результаты недели."],
    )
    due_date: date | None = Field(
        None,
        description="Плановая дата завершения.",
        examples=["2026-08-10"],
    )
    position: float = Field(..., description="Позиция задачи внутри стадии.", examples=[1.0])
    created_at: datetime = Field(
        ...,
        description="Дата создания задачи.",
        examples=["2026-08-01T10:00:00Z"],
    )
    updated_at: datetime = Field(
        ...,
        description="Дата последнего обновления задачи.",
        examples=["2026-08-02T12:00:00Z"],
    )
    wbs_code: str | None = Field(None, description="Код связанного узла ИСР.", examples=["1.1.3"])
    wbs_phase_name: str | None = Field(
        None,
        description="Название корневой фазы ИСР.",
        examples=["Проектирование"],
    )
    comments_count: int = Field(
        0,
        ge=0,
        description="Количество комментариев задачи.",
        examples=[2],
    )
    last_comment: str | None = Field(
        None,
        description="Текст последнего комментария.",
        examples=["Готово к проверке."],
    )
    search_match_source: str | None = Field(
        None,
        description="Источник поискового совпадения.",
        examples=["title"],
    )
    search_title: str | None = Field(
        None,
        description="Заголовок с маркерами подсветки.",
        examples=["__FTS_START__Пользовательская__FTS_END__ инструкция"],
    )
    search_excerpt: str | None = Field(
        None,
        description="Фрагмент совпадения с маркерами подсветки.",
        examples=["Описание __FTS_START__пользовательского__FTS_END__ сценария."],
    )


class TaskCreateSchema(BaseModel):
    """Тело запроса для создания ручной задачи канбана."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Подготовить отчёт",
                "description_md": "Собрать результаты недели.",
                "due_date": "2026-08-10",
                "stage_id": 1,
            }
        }
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Заголовок задачи.",
        examples=["Подготовить отчёт"],
    )
    description_md: str | None = Field(
        None,
        description="Описание задачи в Markdown.",
        examples=["Собрать результаты недели."],
    )
    due_date: date | None = Field(
        None,
        description="Плановая дата завершения.",
        examples=["2026-08-10"],
    )
    stage_id: int | None = Field(
        None,
        gt=0,
        description="Начальная стадия задачи.",
        examples=[1],
    )


class TaskUpdateSchema(BaseModel):
    """Тело запроса для частичного обновления задачи."""

    model_config = ConfigDict(json_schema_extra={"example": {"due_date": "2026-08-10"}})

    title: str | None = Field(
        None,
        min_length=1,
        max_length=512,
        description="Новый заголовок.",
        examples=["Подготовить итоговый отчёт"],
    )
    description_md: str | None = Field(
        None,
        description="Новое описание в Markdown.",
        examples=["Добавить выводы и метрики."],
    )
    due_date: date | None = Field(
        None,
        description="Новая дата завершения или null для очистки.",
        examples=["2026-08-12"],
    )


class TaskMoveSchema(BaseModel):
    """Тело запроса для перемещения задачи."""

    model_config = ConfigDict(json_schema_extra={"example": {"stage_id": 3, "position": 2.0}})

    stage_id: int = Field(..., gt=0, description="Целевая стадия.", examples=[3])
    position: float = Field(..., ge=0, description="Новая позиция внутри стадии.", examples=[2.0])
