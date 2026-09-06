import pytest

from src.knowledge.retrieval import reciprocal_rank_fusion


def test_rrf_merges_rankings_without_double_counting() -> None:
    """Слияние лексического и векторного списков: дубликаты не удваиваются, одинаковые численные идентификаторы разных типов не сливаются, порядок при равных оценках стабилен."""

    scores = reciprocal_rank_fusion(
        [
            ["task:1", "document:2", "task:3"],
            ["document:2", "comment:4", "task:1"],
        ]
    )

    assert list(scores) == ["document:2", "task:1", "comment:4", "task:3"]
    assert scores["document:2"] > scores["comment:4"]

    scores = reciprocal_rank_fusion([["task:5"], ["document:5"]])

    assert set(scores) == {"task:5", "document:5"}

    scores_with_duplicate = reciprocal_rank_fusion([["task:1", "task:1", "task:2"]])
    scores_without_duplicate = reciprocal_rank_fusion([["task:1", "task:2"]])

    assert scores_with_duplicate == scores_without_duplicate

    scores = reciprocal_rank_fusion([["task:2", "task:1"]])

    assert list(scores) == ["task:2", "task:1"]


def test_rrf_rejects_non_positive_rank_constant() -> None:
    with pytest.raises(ValueError, match="положительной"):
        reciprocal_rank_fusion([["task:1"]], rank_constant=0)
