from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SeedState(Base):
    """Маркер успешно завершённой одноразовой загрузки начальных данных."""

    __tablename__ = "seed_state"

    key: Mapped[str] = mapped_column(
        String(length=100),
        primary_key=True,
        doc="Уникальный ключ набора начальных данных.",
        comment="Версионированный ключ успешно загруженного набора данных.",
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Дата успешного завершения загрузки.",
        comment="Дата и время успешной загрузки набора начальных данных.",
    )

    def __repr__(self) -> str:
        return f"<SeedState(key={self.key!r}, completed_at={self.completed_at!r})>"
