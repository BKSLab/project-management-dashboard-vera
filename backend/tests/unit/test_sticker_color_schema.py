"""Цвет стикера — свободный hex, как у стадии канбана (миграция 0008)."""

import pytest
from pydantic import ValidationError

from src.schemas.board_shapes import BoardShapeToStickerSchema
from src.schemas.project_stickers import (
    ProjectStickerCreateSchema,
    ProjectStickerUpdateSchema,
)


def test_create_defaults_to_yellow_hex() -> None:
    assert ProjectStickerCreateSchema(body="Заметка").color == "#fff19a"


@pytest.mark.parametrize("value", ["#7C1623", "#7c1623", " #7C1623 "])
def test_hex_is_stored_lowercase(value: str) -> None:
    assert ProjectStickerCreateSchema(body="x", color=value).color == "#7c1623"


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [("yellow", "#fff19a"), ("Blue", "#c9edff"), ("violet", "#e4d2ff"), ("neutral", "#f3efe4")],
)
def test_legacy_palette_names_become_hex(legacy: str, expected: str) -> None:
    assert ProjectStickerUpdateSchema(revision=1, color=legacy).color == expected
    assert BoardShapeToStickerSchema(color=legacy).color == expected


@pytest.mark.parametrize("value", ["#fff", "fff7bf", "#fff19a00", "#ggg000", "orange", ""])
def test_not_a_six_digit_hex_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        ProjectStickerCreateSchema(body="x", color=value)
    with pytest.raises(ValidationError):
        BoardShapeToStickerSchema(color=value)


def test_update_rejects_explicit_null_color() -> None:
    with pytest.raises(ValidationError):
        ProjectStickerUpdateSchema(revision=1, color=None)
