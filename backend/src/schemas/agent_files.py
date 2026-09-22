from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentFileSchema(BaseModel):
    """Публичная ссылка на приватную загрузку без путей хранилища."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(description="ID загруженного файла.")
    original_name: str = Field(description="Название файла.")
    content_type: str = Field(description="Тип содержимого.")
    size: int = Field(description="Размер в байтах.")
    created_at: datetime = Field(description="Время загрузки.")
