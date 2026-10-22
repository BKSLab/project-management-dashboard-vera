"""Журнал обращений по сервисному API-ключу .

``api_keys.last_used_at`` отвечает только на вопрос «жив ли ключ», а
владельцу нужно видеть, что именно делает интеграция: какие методы
REST и какие инструменты MCP, с каким результатом и как долго. Строка — одно
обращение; статистика считается запросами по этой таблице.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ApiKeyUsage(Base):
    """Одно обращение по сервисному ключу."""

    __tablename__ = "api_key_usage"
    __table_args__ = (
        Index("ix_api_key_usage_key_at", "api_key_id", "at"),
        Index("ix_api_key_usage_at", "at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        doc="Идентификатор записи.",
        comment="Уникальный идентификатор обращения.",
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=True,
        doc="Ключ обращения.",
        comment="Ключ, которым выполнен запрос.",
    )
    key_prefix: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        doc="Префикс ключа на момент обращения.",
        comment="Снимок префикса: читается и после удаления ключа.",
    )
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Момент обращения (UTC).",
        comment="Время начала обработки запроса.",
    )
    channel: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        doc="Канал: rest или mcp.",
        comment="REST-запрос или вызов инструмента MCP.",
    )
    method: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        doc="HTTP-метод; у MCP — CALL.",
        comment="HTTP-метод запроса или CALL для инструмента MCP.",
    )
    route: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Шаблон маршрута или имя инструмента.",
        comment="По нему группируется статистика.",
    )
    path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="Фактический путь или имя инструмента.",
        comment="Без строки запроса — параметры лежат в query.",
    )
    query: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Параметры запроса.",
        comment="Значения усечены; секреты сюда не попадают.",
    )
    actor_login: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Локальный владелец, выполнивший запрос.",
        comment="Логин локального владельца ключа.",
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Код ответа; у MCP — 200 или 400.",
        comment="2xx — успех, 4xx — ошибка клиента, 5xx — сбой сервиса.",
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Длительность в миллисекундах.",
        comment="Замер вокруг обработки запроса.",
    )
    response_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Размер ответа в байтах.",
        comment="Объём отданных данных, если известен.",
    )
    client_ip: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="Адрес источника.",
        comment="Из X-Forwarded-For или адреса соединения.",
    )

    def __repr__(self) -> str:
        return f"<ApiKeyUsage(route={self.route!r}, status={self.status_code}, at={self.at})>"
