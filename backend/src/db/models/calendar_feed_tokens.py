from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class CalendarFeedToken(Base, TimestampMixin):
    """Секрет ссылки подписки на личный календарь (.ics).

    Один на пользователя: перевыпуск заменяет хеш, и старая ссылка сразу
    перестаёт работать. Секрет хранится только как SHA-256 — ссылку
    показывают один раз при выпуске. ``created_at`` — момент последнего
    выпуска.
    """

    __tablename__ = "calendar_feed_tokens"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор записи.",
        comment="Уникальный идентификатор ссылки подписки.",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        doc="Владелец ссылки.",
        comment="Пользователь, чей календарь отдаёт ссылка; одна ссылка на пользователя.",
    )
    token_hash: Mapped[str] = mapped_column(
        String(length=64),
        nullable=False,
        unique=True,
        doc="SHA-256 от секрета в шестнадцатеричном виде.",
        comment="Хеш секрета ссылки подписки; сам секрет не хранится.",
    )
