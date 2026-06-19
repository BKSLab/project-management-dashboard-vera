from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    """Редактируемый markdown-документ проектной документации."""

    __tablename__ = 'documents'

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(
        String(length=255),
        unique=True,
        nullable=False,
        index=True,
        doc='URL-идентификатор документа.'
    )
    title: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        doc='Заголовок для списка документов.'
    )
    content_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc='Markdown-содержимое документа.'
    )

    def __repr__(self) -> str:
        return f'<Document(slug={self.slug})>'
