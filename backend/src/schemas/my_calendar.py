"""Контракт личного календаря, календаря портфеля, производственного календаря и ICS.

Подробное описание полей и правил — ``docs/calendar.md``.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.db.models.project_milestones import ProjectMilestoneStatus
from src.db.models.projects import ProjectStatus
from src.schemas.calendar import CalendarMilestoneSchema, CalendarRangeSchema, CalendarTaskSchema
from src.schemas.enums import TaskKind, TaskStatus


class CalendarSourceSchema(BaseModel):
    """Календарь проектных и разовых задач с доступом по локальным назначениям."""

    kind: TaskKind = Field(..., description="PROJECT или PERSONAL.", examples=["PROJECT"])
    id: int | None = Field(None, description="Идентификатор проекта; у разовой null.")
    key: str | None = Field(None, description="Ключ проекта; у разовой null.")
    name: str | None = Field(None, description="Название проекта; у разовой null.")
    color: str | None = Field(None, description="Цвет проекта; у разовой null.")
    icon: str | None = Field(None, description="Иконка проекта; у разовой null.")
    icon_image_version: str | None = Field(None, description="Версия локальной картинки проекта.")


class MyCalendarTaskSchema(CalendarTaskSchema):
    """Задача личного календаря: поля календаря проекта плюс источник и состояние."""

    stage_id: int | None = Field(None, description="Стадия проектной задачи; вне проекта null.")
    source: CalendarSourceSchema
    state: TaskStatus = Field(..., description="Общее состояние задачи любого вида.")
    state_label: str = Field(..., description="Подпись состояния: имя стадии или статуса.")


class CalendarProjectRefSchema(BaseModel):
    """Короткая ссылка на проект."""

    id: int
    key: str
    name: str
    color: str


class MyCalendarMilestoneSchema(CalendarMilestoneSchema):
    """Веха проекта, где пользователь в команде."""

    project: CalendarProjectRefSchema


class MyCalendarSummarySchema(BaseModel):
    """Счётчики моих незавершённых задач по всем источникам, без учёта диапазона."""

    overdue: int = Field(..., ge=0)
    due_soon: int = Field(..., ge=0)
    unscheduled: int = Field(..., ge=0)


class MyCalendarResponseSchema(BaseModel):
    """Мой календарь в выбранном диапазоне."""

    range: CalendarRangeSchema
    tasks: list[MyCalendarTaskSchema]
    milestones: list[MyCalendarMilestoneSchema]
    summary: MyCalendarSummarySchema
    truncated: bool = Field(
        False, description="true — задач в диапазоне больше предела, отдана первая часть."
    )


class MyUnscheduledTasksPageSchema(BaseModel):
    """Страница моих незавершённых задач без дат."""

    items: list[MyCalendarTaskSchema]
    next_cursor: int | None = None


class PortfolioMilestoneSchema(BaseModel):
    """Веха проекта на полосе портфеля."""

    id: int | None = Field(None, description="null у системной вехи «Дедлайн проекта».")
    title: str
    due_date: date
    status: ProjectMilestoneStatus
    is_system: bool = False


class PortfolioCalendarProjectSchema(BaseModel):
    """Проект на временной шкале портфеля."""

    id: int
    key: str
    name: str
    color: str
    icon: str | None
    icon_image_version: str | None
    status: ProjectStatus
    start_date: date | None
    due_date: date | None
    is_unscheduled: bool = Field(
        False, description="true — у проекта нет ни начала, ни срока; такие идут в конце."
    )
    completion_rate: float = Field(..., ge=0, le=1)
    total_tasks: int = Field(..., ge=0)
    overdue_tasks: int = Field(..., ge=0)
    milestones: list[PortfolioMilestoneSchema]


class PortfolioCalendarResponseSchema(BaseModel):
    """Проекты, пересекающие диапазон, плюс проекты без дат."""

    range: CalendarRangeSchema
    projects: list[PortfolioCalendarProjectSchema]


class HolidayKind(str, Enum):
    """Вид отклонения от обычной пятидневки."""

    HOLIDAY = "HOLIDAY"
    DAY_OFF = "DAY_OFF"
    WORKING_DAY = "WORKING_DAY"
    SHORT_DAY = "SHORT_DAY"


class HolidayDaySchema(BaseModel):
    """День производственного календаря, отличающийся от обычной пятидневки."""

    date: date
    kind: HolidayKind
    title: str


class HolidaysResponseSchema(BaseModel):
    """Производственный календарь РФ на год."""

    year: int
    known: bool = Field(..., description="false — данных на этот год нет, days пуст.")
    source: str | None = Field(None, description="Постановление Правительства о переносе.")
    days: list[HolidayDaySchema]


class IcsTokenSchema(BaseModel):
    """Состояние ссылки подписки на календарь."""

    exists: bool
    created_at: datetime | None = None
    url: str | None = Field(
        None, description="Полная ссылка подписки; только в ответе на выпуск (POST)."
    )
