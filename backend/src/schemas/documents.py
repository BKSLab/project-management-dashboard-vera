from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentSchema(BaseModel):
    """Краткая схема документа для списка."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    updated_at: datetime


class DocumentDetailSchema(DocumentSchema):
    """Полная схема документа с содержимым."""

    content_md: str
    created_at: datetime


class DocumentUpdateSchema(BaseModel):
    """Схема обновления документа."""

    title: Optional[str] = Field(default=None, max_length=255)
    content_md: Optional[str] = None


class DocumentCreateSchema(BaseModel):
    """Схема создания документа."""

    title: str = Field(max_length=255)
    slug: Optional[str] = Field(default=None, max_length=255)
    content_md: str = ""
