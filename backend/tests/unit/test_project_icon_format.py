"""Формат иконки проекта: lucide:<имя> из набора или прежнее эмодзи."""

import pytest
from pydantic import ValidationError

from src.schemas.projects import ProjectUpdateSchema


def test_icon_accepts_lucide_names_emoji_and_clearing() -> None:
    cases = {"lucide:rocket": "lucide:rocket", "lucide:bar-chart-3": "lucide:bar-chart-3"}
    cases |= {"🚀": "🚀", "  ": None, "": None}
    for raw, expected in cases.items():
        assert ProjectUpdateSchema(icon=raw).icon == expected
    assert ProjectUpdateSchema(icon=None).icon is None


@pytest.mark.parametrize(
    "raw", ["lucide:", "lucide:Rocket", "lucide:rocket;alert(1)", "lucide:../x", "длинное эмодзи"]
)
def test_icon_rejects_malformed_values(raw: str) -> None:
    with pytest.raises(ValidationError):
        ProjectUpdateSchema(icon=raw)
