"""Неизменяемые версии единого отчёта по задаче."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TaskReport(Base):
    """Каждая публикация сохраняет полный текст и происхождение результата."""

    __tablename__ = "task_reports"
    __table_args__ = (
        UniqueConstraint("task_id", "revision", name="uq_task_reports_revision"),
        CheckConstraint("revision > 0", name="ck_task_reports_revision"),
    )
    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Версия отчёта.", comment="ID версии отчёта."
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        doc="Задача.",
        comment="Задача отчёта.",
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="Номер версии.", comment="Монотонный номер публикации."
    )
    body_md: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Полный результат.", comment="Снимок текста отчёта."
    )
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        doc="Публикатор.",
        comment="Кто опубликовал версию.",
    )
    author_name: Mapped[str] = mapped_column(
        String(255), nullable=False, doc="Подпись автора.", comment="Снимок имени публикатора."
    )
    source_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_comments.id", ondelete="SET NULL"),
        doc="Исходный комментарий.",
        comment="Ссылка на существующий комментарий.",
    )
    source_comment_original_id: Mapped[int | None] = mapped_column(
        Integer,
        doc="Первоначальный ID.",
        comment="ID источника сохраняется после удаления комментария.",
    )
    source_author_name: Mapped[str | None] = mapped_column(
        String(255), doc="Автор источника.", comment="Снимок автора комментария."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Время публикации.",
        comment="Дата публикации версии.",
    )
