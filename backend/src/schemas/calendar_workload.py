"""Контракт загрузки команды проекта по дням (``docs/calendar.md``, «Загрузка»)."""

from datetime import date

from pydantic import BaseModel, Field


class WorkloadDaySchema(BaseModel):
    """Нагрузка человека в один рабочий день; дни без нагрузки не передаются."""

    date: date
    project_tasks: int = Field(
        ..., description="Открытых задач этого проекта в работе в этот день."
    )
    project_keys: list[str] = Field(
        default_factory=list, description="Ключи задач этого проекта в работе в этот день."
    )
    other_tasks: int = Field(
        ..., description="Открытых задач вне этого проекта (другие проекты и разовые)."
    )
    other_keys: list[str] = Field(
        default_factory=list,
        description=(
            "Ключи задач вне проекта, которые смотрящему видны. Остальные входят только "
            "в счётчик other_tasks."
        ),
    )
    level: int = Field(
        ...,
        ge=0,
        le=3,
        description="Ступень суммарной загрузки: 1 — норма, 2 — плотно, 3 — перегруз.",
    )


class WorkloadOtherTaskSchema(BaseModel):
    """Видимая смотрящему задача человека вне этого проекта."""

    key: str
    title: str
    source_name: str = Field(..., description="Проект или «Разовые задачи».")
    start_date: date | None
    due_date: date | None


class WorkloadPersonSchema(BaseModel):
    """Участник команды проекта с нагрузкой по дням."""

    user_id: int
    name: str = Field(
        ..., description="Подпись, совпадающая с полем assignee задач календаря проекта."
    )
    days: list[WorkloadDaySchema]
    other_tasks: list[WorkloadOtherTaskSchema] = Field(
        default_factory=list,
        description="Видимые смотрящему задачи вне проекта в периоде.",
    )
    other_hidden: int = Field(
        0, description="Сколько задач вне проекта в периоде скрыто: у смотрящего нет доступа."
    )


class CalendarWorkloadResponseSchema(BaseModel):
    """Загрузка команды проекта в периоде."""

    date_from: date
    date_to: date
    people: list[WorkloadPersonSchema]
    truncated: bool = Field(False, description="Задач оказалось больше предела — расчёт неполный.")
