from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Computed, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .projects import Project


class Document(Base, TimestampMixin):
    """Редактируемый markdown-документ проекта."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_documents_project_slug"),
        Index("ix_documents_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор документа.",
        comment="Уникальный идентификатор документа.",
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Проект, которому принадлежит документ.",
        comment="Идентификатор проекта-владельца документа.",
    )
    slug: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        index=True,
        doc="URL-идентификатор документа, уникальный в пределах проекта.",
        comment="URL-идентификатор документа внутри проекта.",
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

    project: Mapped[Project] = relationship("Project", back_populates="documents")

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, project_id={self.project_id}, slug={self.slug!r})>"
