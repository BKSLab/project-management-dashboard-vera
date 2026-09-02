from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.db.models.project_milestones import ProjectMilestoneStatus


class MilestoneSchema(BaseModel):
    """Пользовательская проектная веха."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    due_date: date
    status: ProjectMilestoneStatus
    wbs_node_id: int | None
    description_md: str | None
    created_at: datetime
    updated_at: datetime


class MilestoneCreateSchema(BaseModel):
    """Тело создания простой проектной вехи."""

    title: str = Field(..., min_length=1, max_length=255)
    due_date: date
    status: ProjectMilestoneStatus = ProjectMilestoneStatus.PLANNED
    wbs_node_id: int | None = Field(None, gt=0)
    description_md: str | None = None


class MilestoneUpdateSchema(BaseModel):
    """Тело частичного обновления проектной вехи."""

    title: str | None = Field(None, min_length=1, max_length=255)
    due_date: date | None = None
    status: ProjectMilestoneStatus | None = None
    wbs_node_id: int | None = Field(None, gt=0)
    description_md: str | None = None

    @field_validator("title", "due_date", "status")
    @classmethod
    def required_fields_cannot_be_cleared(cls, value):
        """Не позволяет очистить обязательные поля через PATCH."""
        if value is None:
            raise ValueError("Обязательное поле нельзя очистить.")
        return value
