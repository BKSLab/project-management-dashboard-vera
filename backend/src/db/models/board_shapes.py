from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class BoardShapeKind(str, enum.Enum):
    """Вид фигуры на доске."""

    RECT = "rect"
    ELLIPSE = "ellipse"
    DIAMOND = "diamond"
    TEXT = "text"
    ARROW = "arrow"
    LINE = "line"


LINEAR_KINDS = frozenset({BoardShapeKind.ARROW, BoardShapeKind.LINE})


class BoardShape(Base, TimestampMixin):
    """Фигура, стрелка, линия или надпись на доске проекта."""

    __tablename__ = "board_shapes"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_board_shapes_revision_positive"),
        CheckConstraint(
            "x BETWEEN -1000000.0 AND 1000000.0 AND y BETWEEN -1000000.0 AND 1000000.0",
            name="ck_board_shapes_xy_range",
        ),
        CheckConstraint(
            "kind IN ('arrow', 'line') OR (w BETWEEN 1.0 AND 20000.0 AND h BETWEEN 1.0 AND 20000.0)",
            name="ck_board_shapes_box_size",
        ),
        CheckConstraint(
            "w BETWEEN 0.0 AND 2000000.0 AND h BETWEEN 0.0 AND 2000000.0",
            name="ck_board_shapes_size_range",
        ),
        CheckConstraint(
            "(kind IN ('arrow', 'line')) = (points IS NOT NULL)",
            name="ck_board_shapes_points_only_linear",
        ),
        CheckConstraint(
            "kind IN ('arrow', 'line') OR (start_ref IS NULL AND end_ref IS NULL)",
            name="ck_board_shapes_refs_only_linear",
        ),
        CheckConstraint("char_length(label) <= 2000", name="ck_board_shapes_label_length"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор фигуры.",
        comment="Уникальный идентификатор фигуры доски.",
    )
    board_id: Mapped[int] = mapped_column(
        ForeignKey("project_boards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Доска, на которой нарисована фигура.",
        comment="Идентификатор доски; фигура удаляется вместе с доской.",
    )
    kind: Mapped[BoardShapeKind] = mapped_column(
        Enum(
            BoardShapeKind,
            name="board_shape_kind",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        doc="Вид фигуры.",
        comment="rect, ellipse, diamond, text, arrow или line.",
    )
    x: Mapped[float] = mapped_column(
        Float, nullable=False, doc="Левый край рамки.", comment="X левого верхнего угла рамки."
    )
    y: Mapped[float] = mapped_column(
        Float, nullable=False, doc="Верхний край рамки.", comment="Y левого верхнего угла рамки."
    )
    w: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Ширина рамки; у стрелки и линии считается по точкам.",
        comment="Ширина рамки фигуры на холсте.",
    )
    h: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Высота рамки; у стрелки и линии считается по точкам.",
        comment="Высота рамки фигуры на холсте.",
    )
    points: Mapped[list[list[float]] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
        doc="Точки стрелки или линии [[x, y], …] в координатах холста.",
        comment="Ломаная стрелки/линии; NULL у остальных фигур.",
    )
    start_ref: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
        doc="Объект, к которому прицеплено начало стрелки.",
        comment='Привязка начала: {"type", "id", "anchor"}; только у arrow/line.',
    )
    end_ref: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
        doc="Объект, к которому прицеплен конец стрелки.",
        comment='Привязка конца: {"type", "id", "anchor"}; только у arrow/line.',
    )
    style: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc="Полный стиль фигуры, дополненный сервером умолчаниями.",
        comment="Цвета-токены палитры, толщина, пунктир, наконечники, шрифт.",
    )
    label: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
        doc="Подпись фигуры без HTML.",
        comment="Текст внутри фигуры или надпись.",
    )
    z_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Слой: общая шкала со стикерами той же доски.",
        comment="Порядок наложения на доске.",
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="Автор фигуры, если профиль ещё существует.",
        comment="Идентификатор автора фигуры.",
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        doc="Версия для optimistic concurrency.",
        comment="Монотонная ревизия фигуры.",
    )

    def __repr__(self) -> str:
        return (
            f"<BoardShape(id={self.id}, board_id={self.board_id}, kind={self.kind.value}, "
            f"revision={self.revision})>"
        )
