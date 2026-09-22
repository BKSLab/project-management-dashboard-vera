"""Бюджет каждого раунда, продолжения страниц и сохранность квитанций."""

import json

from src.agent.context import AgentContextBudget


def test_repeated_reads_replace_same_page_but_keep_other_pages_and_current_receipt():
    budget = AgentContextBudget(system_prompt="Инструкция", max_tokens=1800, history_tokens=200)
    content = {
        "question": "Сравни условия",
        "read_results": [],
        "retrieval_context": [{"source_id": "document:1", "text": "Описание"}],
    }
    budget.prepare(content)
    for _ in range(3):
        budget.add_result(
            content,
            request={"name": "read_source", "arguments": {"source_id": "document:1", "offset": 0}},
            result={"source_id": "document:1", "source_handle": "SRC_1", "text": "Первая страница"},
        )
    assert len(content["read_results"]) == 1
    budget.add_result(
        content,
        request={"name": "read_source", "arguments": {"offset": 0, "source_id": "document:1"}},
        result={
            "source_id": "document:1",
            "source_handle": "SRC_1",
            "text": "Актуальная страница",
            "offset": 0,
        },
    )
    assert len(content["read_results"]) == 1
    assert content["read_results"][0]["result"]["text"] == "Актуальная страница"
    assert content["retrieval_context"] == []
    budget.add_result(
        content,
        request={"name": "read_source", "arguments": {"source_id": "document:1", "offset": 4000}},
        result={"source_id": "document:1", "source_handle": "SRC_1", "text": "Вторая страница"},
    )
    assert len(content["read_results"]) == 2
    for i in range(6):
        budget.add_result(
            content,
            request={"name": "read_source", "arguments": {"source_id": f"document:{i + 2}"}},
            result={
                "source_id": f"document:{i + 2}",
                "source_handle": f"SRC_{i + 2}",
                "text": "Длинный текст. " * 1000,
                "offset": 0,
                "total_chars": 14000,
                "next_offset": None,
            },
        )
        output = budget.fit(content)
        assert budget.tokens(content) <= 1800
        assert json.loads(output)["question"] == "Сравни условия"
    action = {
        "id": 42,
        "tool_name": "create_document",
        "title": "Документ создан",
        "status": "completed",
        "result": {
            "source_id": "document:99",
            "document": {"id": 99, "title": "Новый", "content_md": "Огромный текст" * 10000},
        },
    }
    budget.add_result(
        content,
        request={"name": "create_document", "arguments": {"content_md": "Огромный текст" * 10000}},
        result={"action": action},
    )
    budget.fit(content)
    receipt = content["read_results"][-1]["result"]["action"]
    assert receipt["status"] == "completed"
    assert receipt["id"] == 42
    assert receipt["result"]["document"]["id"] == 99
    assert "content_md" in receipt["result"]["document"]["omitted_fields"]
    assert budget.tokens(content) <= 1800
    # Сохранённый результат для интерфейса не изменяется сокращением prompt.
    assert len(action["result"]["document"]["content_md"]) > 100000


def test_budget_shrinks_large_page_without_skipping_unseen_items_or_text():
    budget = AgentContextBudget(system_prompt="Инструкция", max_tokens=1700, history_tokens=200)
    result = {
        "items": [{"source_id": f"task:{i}", "text": "Подробности. " * 100} for i in range(20, 50)],
        "offset": 20,
        "next_offset": 50,
        "total": 80,
    }
    content = {
        "question": "Покажи задачи",
        "read_results": [{"request": {"name": "list_sources"}, "result": result}],
    }
    budget.fit(content)
    assert 0 < len(result["items"]) < 30
    assert result["next_offset"] == 20 + len(result["items"])
    assert len(result["items"]) + result["items_omitted"] == 30
    assert result["total"] == 80
    page = {
        "source_id": "document:1",
        "text": "Содержимое. " * 2000,
        "offset": 500,
        "total_chars": 22500,
        "next_offset": None,
    }
    content["read_results"] = [{"request": {"name": "read_source"}, "result": page}]
    budget.fit(content)
    assert page["next_offset"] == 500 + len(page["text"])
    assert page["text_truncated"]


def test_history_budget_keeps_recent_messages_and_marks_omissions():
    budget = AgentContextBudget(system_prompt="Правила", max_tokens=2000, history_tokens=150)
    content = {
        "dialog_history": [
            {"role": "user", "content": str(i) + " реплика " * 20} for i in range(10)
        ],
        "dialog_memory": "Память " * 1000,
    }
    budget.prepare(content)
    assert content["dialog_history"][-1]["content"].startswith("9")
    assert content["dialog_history_omitted"] > 0
    assert "память сокращена" in content["dialog_memory"]


def test_shortened_reply_keeps_card_ids_at_the_end():
    budget = AgentContextBudget(system_prompt="Правила", max_tokens=2000, history_tokens=150)
    content = {
        "dialog_history": [
            {
                "role": "assistant",
                "content": "Вывод: "
                + "Длинное объяснение. " * 200
                + "\nИсточники: task:777 — Приёмка",
            }
        ]
    }
    budget.prepare(content)
    assert content["dialog_history"][0]["content"].startswith("Вывод:")
    assert "task:777" in content["dialog_history"][0]["content"]
