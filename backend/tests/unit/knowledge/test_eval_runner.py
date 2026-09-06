import json
from pathlib import Path

import pytest

from evals.knowledge_retrieval.runner import (
    RetrievalExample,
    calculate_metrics,
    load_retrieval_examples,
    run,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
CANDIDATES = (
    Path(__file__).resolve().parents[3]
    / "evals"
    / "knowledge_retrieval"
    / "candidate_questions.json"
)


def test_runner_calculates_recall_at_k_and_mrr_on_known_fixture() -> None:
    result = run(
        FIXTURES / "knowledge_eval_dataset.json",
        FIXTURES / "knowledge_eval_predictions.json",
        (1, 2, 3),
    )

    assert result["examples_count"] == 2
    assert result["recall_at_k"] == {"1": 0.25, "2": 0.75, "3": 1.0}
    assert result["mrr"] == 0.75


def test_metrics_ignore_duplicate_prediction_ids() -> None:
    examples = [
        RetrievalExample(
            example_id="one",
            question="Вопрос",
            gold_source_ids=frozenset({"task:1"}),
        )
    ]

    metrics = calculate_metrics(
        examples,
        {"one": ["task:2", "task:2", "task:1"]},
        k_values=(1, 2),
    )

    assert metrics.recall_at_k == {"1": 0.0, "2": 1.0}
    assert metrics.mrr == 0.5


def test_eval_fixture_is_valid_and_unapproved_candidates_are_blocked(tmp_path: Path) -> None:
    """Неодобренные кандидаты не запускаются, пустой эталон отвергается, файл кандидатов не содержит одобренных вопросов."""

    dataset = tmp_path / "candidates.json"
    dataset.write_text(
        json.dumps(
            {
                "examples": [
                    {
                        "id": "candidate",
                        "kind": "semantic",
                        "approval_status": "ТРЕБУЕТ УТВЕРЖДЕНИЯ",
                        "question": "Вопрос",
                        "gold_source_ids": ["task:1"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="не утверждён"):
        load_retrieval_examples(dataset)

    dataset = tmp_path / "empty.json"
    dataset.write_text(
        json.dumps(
            {
                "examples": [
                    {
                        "id": "approved",
                        "kind": "hybrid",
                        "approval_status": "APPROVED",
                        "question": "Вопрос",
                        "gold_source_ids": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ground truth"):
        load_retrieval_examples(dataset)

    payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))

    assert "ТРЕБУЕТ УТВЕРЖДЕНИЯ" in payload["notice"]
    assert 30 <= len(payload["examples"]) <= 50
    assert all(item["approval_status"] == "ТРЕБУЕТ УТВЕРЖДЕНИЯ" for item in payload["examples"])
    assert all("gold_source_ids" not in item for item in payload["examples"])
