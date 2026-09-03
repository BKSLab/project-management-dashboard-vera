from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.db.models.project_members import ProjectRole
from src.schemas.users import USERNAME_PATTERN, UserSummarySchema


class ProjectMemberSchema(BaseModel):
    """Участник проектной команды без приватных контактных данных."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Идентификатор участия.", examples=[12])
    project_id: int = Field(..., description="Идентификатор проекта.", examples=[1])
    role: ProjectRole = Field(..., description="Роль доступа в проекте.", examples=["MEMBER"])
    user: UserSummarySchema = Field(..., description="Публичная идентичность участника.")
    created_at: datetime = Field(..., description="Дата добавления в команду.")


class ProjectMemberCreateSchema(BaseModel):
    """Добавление пользователя в команду по известному точному логину."""

    username: str = Field(
        ...,
        pattern=USERNAME_PATTERN,
        description="Точный логин без поиска и автодополнения.",
        examples=["boris"],
    )

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        """Убирает случайные пробелы и нормализует регистр логина."""
        return value.strip().lower() if isinstance(value, str) else value
