import pytest

from src.prompts.analytics import ANALYTICS_SYSTEM_PROMPT
from src.prompts.base import (
    LANGUAGE_RULE,
    PM_ROLE,
    TRACKER_CONTEXT,
    UNTRUSTED_DATA_RULE,
    build_system_prompt,
)
from src.prompts.project_agent import (
    PROJECT_AGENT_SYSTEM_PROMPT,
    PROJECT_AGENT_TOOL_SELECTION_PROMPT,
)
from src.prompts.task_description import TASK_DESCRIPTION_REPHRASE_PROMPT
from src.prompts.wbs_suggestion import WBS_SUGGESTION_SYSTEM_PROMPT

ALL_PROMPTS = {
    "analytics": ANALYTICS_SYSTEM_PROMPT,
    "wbs_suggestion": WBS_SUGGESTION_SYSTEM_PROMPT,
    "task_description": TASK_DESCRIPTION_REPHRASE_PROMPT,
    "project_agent": PROJECT_AGENT_SYSTEM_PROMPT,
    "tool_selection": PROJECT_AGENT_TOOL_SELECTION_PROMPT,
}

ROLE_PROMPTS = {name: value for name, value in ALL_PROMPTS.items() if name != "tool_selection"}


@pytest.mark.parametrize("prompt", ALL_PROMPTS.values(), ids=ALL_PROMPTS.keys())
def test_every_prompt_declares_input_as_untrusted(prompt: str) -> None:
    assert UNTRUSTED_DATA_RULE in prompt


@pytest.mark.parametrize("prompt", ROLE_PROMPTS.values(), ids=ROLE_PROMPTS.keys())
def test_reasoning_prompts_share_the_same_role_and_context(prompt: str) -> None:
    assert PM_ROLE in prompt
    assert TRACKER_CONTEXT in prompt


@pytest.mark.parametrize("prompt", ROLE_PROMPTS.values(), ids=ROLE_PROMPTS.keys())
def test_reasoning_prompts_start_with_the_role(prompt: str) -> None:
    assert prompt.startswith(PM_ROLE)


def test_tool_selection_prompt_stays_free_of_role_and_language_rule() -> None:
    assert PM_ROLE not in PROJECT_AGENT_TOOL_SELECTION_PROMPT
    assert TRACKER_CONTEXT not in PROJECT_AGENT_TOOL_SELECTION_PROMPT
    assert LANGUAGE_RULE not in PROJECT_AGENT_TOOL_SELECTION_PROMPT


@pytest.mark.parametrize("prompt", ALL_PROMPTS.values(), ids=ALL_PROMPTS.keys())
def test_every_prompt_declares_its_json_contract(prompt: str) -> None:
    assert "Верни" in prompt
    assert "JSON" in prompt


def test_role_names_the_principles_instead_of_relying_on_a_standard_edition() -> None:
    assert "PMBOK" in PM_ROLE
    # Номер издания намеренно не зашит: модель не получит от него знаний, зато
    # получит повод уверенно сослаться на несуществующее положение.
    assert "правило 100%" in PM_ROLE
    assert "критическим путём" in PM_ROLE
    assert not any(f"PMBOK {number}" in PM_ROLE for number in ("6", "7", "8", "9"))


def test_task_description_keeps_the_ban_on_inventing_facts_under_the_pm_role() -> None:
    assert PM_ROLE in TASK_DESCRIPTION_REPHRASE_PROMPT
    assert "не добавляй факты" in TASK_DESCRIPTION_REPHRASE_PROMPT
    assert "не заполняй догадкой" in TASK_DESCRIPTION_REPHRASE_PROMPT


def test_build_system_prompt_keeps_declared_order_of_blocks() -> None:
    prompt = build_system_prompt("Инструкция операции.")

    assert prompt.index(PM_ROLE) < prompt.index(TRACKER_CONTEXT)
    assert prompt.index(TRACKER_CONTEXT) < prompt.index(UNTRUSTED_DATA_RULE)
    assert prompt.index(UNTRUSTED_DATA_RULE) < prompt.index(LANGUAGE_RULE)
    assert prompt.endswith("Инструкция операции.")


def test_build_system_prompt_without_role_keeps_untrusted_data_rule() -> None:
    prompt = build_system_prompt("Инструкция.", with_role=False, with_language=False)

    assert prompt == f"{UNTRUSTED_DATA_RULE}\n\nИнструкция."
