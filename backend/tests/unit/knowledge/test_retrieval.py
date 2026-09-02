import pytest

from src.knowledge.retrieval import reciprocal_rank_fusion


def test_rrf_merges_lexical_and_vector_candidates() -> None:
    scores = reciprocal_rank_fusion(
        [
            ["task:1", "document:2", "task:3"],
            ["document:2", "comment:4", "task:1"],
        ]
    )

    assert list(scores) == ["document:2", "task:1", "comment:4", "task:3"]
    assert scores["document:2"] > scores["comment:4"]


def test_rrf_keeps_sources_with_same_numeric_entity_id_separate() -> None:
    scores = reciprocal_rank_fusion([["task:5"], ["document:5"]])

    assert set(scores) == {"task:5", "document:5"}


def test_rrf_does_not_count_duplicate_twice_within_one_ranking() -> None:
    scores_with_duplicate = reciprocal_rank_fusion([["task:1", "task:1", "task:2"]])
    scores_without_duplicate = reciprocal_rank_fusion([["task:1", "task:2"]])

    assert scores_with_duplicate == scores_without_duplicate


def test_rrf_uses_stable_first_seen_order_for_equal_scores() -> None:
    scores = reciprocal_rank_fusion([["task:2", "task:1"]])

    assert list(scores) == ["task:2", "task:1"]


def test_rrf_rejects_non_positive_rank_constant() -> None:
    with pytest.raises(ValueError, match="положительной"):
        reciprocal_rank_fusion([["task:1"]], rank_constant=0)
