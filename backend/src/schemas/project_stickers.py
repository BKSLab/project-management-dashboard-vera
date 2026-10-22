from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.db.models.project_stickers import DEFAULT_STICKER_COLOR

MAX_STICKER_BODY_LENGTH = 2000
MAX_STICKER_TASKS = 20
MAX_STICKER_COORDINATE = 1_000_000.0
DEFAULT_STICKER_COORDINATE = 40.0
MIN_STICKER_SIZE = 160.0
MAX_STICKER_SIZE = 520.0
MAX_STICKER_Z_INDEX = 1_000_000_000
STICKER_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"

# Имена прежней палитры (до 0008) принимаются и переводятся в hex — для старых
# клиентов и агентов, которые ещё шлют «yellow». В ответах всегда hex.
LEGACY_STICKER_COLORS: dict[str, str] = {
    "neutral": "#f3efe4",
    "yellow": DEFAULT_STICKER_COLOR,
    "blue": "#c9edff",
    "green": "#d8f5b5",
    "red": "#ffbbb5",
    "violet": "#e4d2ff",
}


def _legacy_color_to_hex(value: Any) -> Any:
    if isinstance(value, str):
        return LEGACY_STICKER_COLORS.get(value.strip().lower(), value.strip())
    return value


StickerColor = Annotated[
    str,
    BeforeValidator(_legacy_color_to_hex),
    Field(
        pattern=STICKER_COLOR_PATTERN,
        description=(
            "Цвет стикера: hex #rrggbb (хранится в нижнем регистре). Имена прежней палитры "
            "neutral/yellow/blue/green/red/violet тоже принимаются и переводятся в hex."
        ),
        examples=["#fff19a"],
    ),
    AfterValidator(str.lower),
]


class ProjectStickerCreateSchema(BaseModel):
    """Создание короткой общей заметки на доске проекта."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1, max_length=MAX_STICKER_BODY_LENGTH)
    color: StickerColor = DEFAULT_STICKER_COLOR
    task_ids: list[int] = Field(default_factory=list, max_length=MAX_STICKER_TASKS)
    canvas_x: float = Field(
        DEFAULT_STICKER_COORDINATE,
        ge=-MAX_STICKER_COORDINATE,
        le=MAX_STICKER_COORDINATE,
    )
    canvas_y: float = Field(
        DEFAULT_STICKER_COORDINATE,
        ge=-MAX_STICKER_COORDINATE,
        le=MAX_STICKER_COORDINATE,
    )
    width: float = Field(
        230.0, ge=MIN_STICKER_SIZE, le=MAX_STICKER_SIZE, description="Ширина стикера."
    )
    height: float = Field(
        230.0, ge=MIN_STICKER_SIZE, le=MAX_STICKER_SIZE, description="Высота стикера."
    )
    z_index: int = Field(
        0, ge=-MAX_STICKER_Z_INDEX, le=MAX_STICKER_Z_INDEX, description="Слой на доске."
    )

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        """Убирает внешние пробелы и запрещает визуально пустой текст."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Текст стикера не может быть пустым.")
        return normalized

    @field_validator("task_ids")
    @classmethod
    def normalize_task_ids(cls, value: list[int]) -> list[int]:
        """Проверяет положительные ID и удаляет повторы с сохранением порядка."""
        if any(task_id <= 0 for task_id in value):
            raise ValueError("Идентификаторы задач должны быть положительными.")
        return list(dict.fromkeys(value))


class ProjectStickerUpdateSchema(BaseModel):
    """Частичное изменение стикера с ожидаемой ревизией."""

    model_config = ConfigDict(extra="forbid")

    revision: int = Field(..., ge=1)
    body: str | None = Field(None, min_length=1, max_length=MAX_STICKER_BODY_LENGTH)
    color: StickerColor | None = None
    task_ids: list[int] | None = Field(None, max_length=MAX_STICKER_TASKS)

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        """Требует хотя бы одно бизнес-изменение и не принимает явный null."""
        changed_fields = self.model_fields_set - {"revision"}
        if not changed_fields:
            raise ValueError("Нужно передать изменение стикера.")
        if "body" in self.model_fields_set:
            if self.body is None:
                raise ValueError("Текст стикера не может быть NULL.")
            self.body = self.body.strip()
            if not self.body:
                raise ValueError("Текст стикера не может быть пустым.")
        if "color" in self.model_fields_set and self.color is None:
            raise ValueError("Цвет стикера не может быть NULL.")
        if "task_ids" in self.model_fields_set:
            if self.task_ids is None:
                raise ValueError("Список задач не может быть NULL.")
            if any(task_id <= 0 for task_id in self.task_ids):
                raise ValueError("Идентификаторы задач должны быть положительными.")
            self.task_ids = list(dict.fromkeys(self.task_ids))
        return self


class ProjectStickerPositionUpdateSchema(BaseModel):
    """Новая позиция стикера на бесконечном холсте."""

    model_config = ConfigDict(extra="forbid")

    canvas_x: float = Field(
        ...,
        ge=-MAX_STICKER_COORDINATE,
        le=MAX_STICKER_COORDINATE,
    )
    canvas_y: float = Field(
        ...,
        ge=-MAX_STICKER_COORDINATE,
        le=MAX_STICKER_COORDINATE,
    )
    width: float | None = Field(
        None, ge=MIN_STICKER_SIZE, le=MAX_STICKER_SIZE, description="Новая ширина."
    )
    height: float | None = Field(
        None, ge=MIN_STICKER_SIZE, le=MAX_STICKER_SIZE, description="Новая высота."
    )
    z_index: int | None = Field(
        None, ge=-MAX_STICKER_Z_INDEX, le=MAX_STICKER_Z_INDEX, description="Новый слой."
    )


class ProjectStickerSchema(BaseModel):
    """Стикер Project Board для безопасного отображения участникам проекта."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    board_id: int
    body: str
    color: str = Field(..., description="Цвет стикера: hex #rrggbb.")
    canvas_x: float
    canvas_y: float
    width: float = Field(230.0, ge=MIN_STICKER_SIZE, le=MAX_STICKER_SIZE)
    height: float = Field(230.0, ge=MIN_STICKER_SIZE, le=MAX_STICKER_SIZE)
    z_index: int = 0
    created_by_user_id: int | None
    created_by_username_snapshot: str
    created_by_display_name_snapshot: str
    task_ids: list[int]
    revision: int
    created_at: datetime
    updated_at: datetime
