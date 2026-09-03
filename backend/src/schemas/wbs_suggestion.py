from pydantic import BaseModel, ConfigDict, Field

MAX_SUGGESTED_NODES = 40
MAX_SUGGESTED_DEPTH = 4


class WbsSuggestedNodeSchema(BaseModel):
    """Предложенный раздел ИСР.

    Раздел ещё не существует в базе: он адресуется временным идентификатором
    ``temp_id``, который живёт только внутри одного предложения. Настоящие
    идентификаторы появляются при применении предложения.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "temp_id": "n2",
                "parent_temp_id": "n1",
                "title": "Проектирование",
                "rationale": "Отдельный этап жизненного цикла до разработки.",
            }
        }
    )

    temp_id: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Временный идентификатор раздела внутри предложения.",
        examples=["n2"],
    )
    parent_temp_id: str | None = Field(
        None,
        max_length=32,
        description="Временный идентификатор родителя; null — верхний уровень.",
        examples=["n1"],
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Название раздела.",
        examples=["Проектирование"],
    )
    rationale: str | None = Field(
        None,
        max_length=500,
        description="Короткое обоснование раздела для пользователя.",
        examples=["Отдельный этап жизненного цикла до разработки."],
    )


class WbsSuggestedAssignmentSchema(BaseModel):
    """Предложенное размещение существующей задачи в разделе."""

    model_config = ConfigDict(json_schema_extra={"example": {"task_id": 142, "node_temp_id": "n2"}})

    task_id: int = Field(
        ..., gt=0, description="Идентификатор существующей задачи.", examples=[142]
    )
    node_temp_id: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Временный идентификатор раздела, в который предлагается задача.",
        examples=["n2"],
    )


class WbsSuggestionSchema(BaseModel):
    """Черновик ИСР, предложенный моделью.

    Предложение ничего не меняет в проекте: это разбор, который пользователь
    правит и применяет отдельным запросом.
    """

    nodes: list[WbsSuggestedNodeSchema] = Field(
        default_factory=list,
        description="Предлагаемые разделы; дерево собирается по parent_temp_id.",
    )
    assignments: list[WbsSuggestedAssignmentSchema] = Field(
        default_factory=list,
        description="Предлагаемое размещение задач по разделам.",
    )
    summary: str = Field(
        "",
        max_length=1000,
        description="Короткое пояснение логики разбиения для пользователя.",
        examples=["Структура разбита по этапам жизненного цикла продукта."],
    )
    skipped_task_ids: list[int] = Field(
        default_factory=list,
        description="Задачи, которым модель не нашла места; они остаются как есть.",
    )


class WbsSuggestionApplySchema(BaseModel):
    """Тело запроса на применение предложения.

    Клиент присылает отредактированный пользователем черновик, поэтому
    backend заново проверяет его целиком и не доверяет исходному ответу
    модели.
    """

    nodes: list[WbsSuggestedNodeSchema] = Field(
        ...,
        min_length=1,
        max_length=MAX_SUGGESTED_NODES,
        description="Разделы, которые нужно создать.",
    )
    assignments: list[WbsSuggestedAssignmentSchema] = Field(
        default_factory=list,
        description="Задачи, которые нужно поместить в созданные разделы.",
    )


class WbsSuggestionApplyResultSchema(BaseModel):
    """Результат применения предложения."""

    created_nodes: int = Field(..., ge=0, description="Сколько разделов создано.", examples=[6])
    assigned_tasks: int = Field(
        ...,
        ge=0,
        description="Сколько задач размещено в новых разделах.",
        examples=[18],
    )
