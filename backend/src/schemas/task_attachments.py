from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskAttachmentSchema(BaseModel):
    """Метаданные прикреплённого к задаче файла."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор файла.", examples=[4])
    task_id: int = Field(..., description="Идентификатор задачи.", examples=[12])
    original_name: str = Field(
        ...,
        description="Исходное имя файла.",
        examples=["Отчёт за август.pdf"],
    )
    content_type: str = Field(
        ...,
        description="MIME-тип файла.",
        examples=["application/pdf"],
    )
    size: int = Field(..., gt=0, description="Размер файла в байтах.", examples=[204800])
    created_at: datetime = Field(
        ...,
        description="Дата и время загрузки файла.",
        examples=["2026-08-02T12:00:00Z"],
    )
    content_url: str = Field(
        ...,
        description="Относительный URL просмотра или скачивания файла.",
        examples=["/api/v1/tasks/12/attachments/4/content"],
    )
    previewable: bool = Field(
        ...,
        description="Можно ли безопасно показать файл как изображение.",
        examples=[False],
    )
