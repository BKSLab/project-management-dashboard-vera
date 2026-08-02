from sqlalchemy import Computed, Index, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    """Редактируемый markdown-документ проектной документации."""

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_search_vector", "search_vector", postgresql_using="gin"),)

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор документа.",
        comment="Уникальный идентификатор документа.",
    )
    slug: Mapped[str] = mapped_column(
        String(length=255),
        unique=True,
        nullable=False,
        index=True,
        doc="URL-идентификатор документа.",
        comment="Уникальный URL-идентификатор документа.",
    )
    title: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        doc="Заголовок для списка документов.",
        comment="Человекочитаемый заголовок документа.",
    )
    content_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Markdown-содержимое документа.",
        comment="Содержимое документа в формате Markdown.",
    )
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('russian', coalesce(content_md, '')), 'B')",
            persisted=True,
        ),
        nullable=False,
        doc="Автоматически вычисляемый FTS-вектор заголовка и содержимого документа.",
        comment="Взвешенный FTS-вектор заголовка и содержимого документа.",
    )

    def __repr__(self) -> str:
        return f"<Document(slug={self.slug})>"
