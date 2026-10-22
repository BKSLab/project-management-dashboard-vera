"""Вера вызывается целым именем в начале сообщения, без старого обращения «Тим»."""

from src.agent.tim import TIM_NAME, TimMode, is_addressed_to_tim, strip_address
from src.prompts.project_agent import TIM_SYSTEM_PROMPTS
from src.prompts.tracker_agent import TRACKER_ROUTER_SYSTEM_PROMPT


def test_message_is_for_vera_only_when_it_starts_with_the_whole_word():
    addressed = [
        "Вера, что горит?",
        "ВЕРА перенеси срок",
        "вера",
        "  Вера: сводка по проекту  ",
        "вера!",
        "Вера\nкакие задачи?",
        "ВеРа — сводка",
        "Вера, PM-план готов?",
    ]
    not_addressed = [
        "Веранда, привет",
        "Вероника сказала",
        "коллеги, Вера сказала",
        "@Вера привет",
        "",
        None,
        "вера2 это логин",
        "ВераO отчёт",
        "Тим, сводка",
        "ТИМ перенеси срок",
        "тим",
    ]
    wrong = [text for text in addressed if not is_addressed_to_tim(text)]
    wrong += [text for text in not_addressed if is_addressed_to_tim(text)]
    assert not wrong, f"Адресация распознана неверно: {wrong}"


def test_strip_address_keeps_the_question_itself():
    cases = {
        "Вера, какие задачи в проекте?": "какие задачи в проекте?",
        "ВЕРА перенеси срок": "перенеси срок",
        "вера: — сводка": "сводка",
        "Вера": "Вера",
        "Веранда, привет": "Веранда, привет",
        "Вероника, привет": "Вероника, привет",
        "Вера, PM-план готов?": "PM-план готов?",
        "Вера PMO отчёт": "PMO отчёт",
        "Вера PM: сводка": "PM: сводка",
        "Тим, сводка": "Тим, сводка",
        "коллеги, Вера, сводка": "коллеги, Вера, сводка",
    }
    assert {text: strip_address(text) for text in cases} == cases


def test_agent_identity_and_persona_are_vera_project_manager_in_every_mode():
    assert TIM_NAME == "Вера"
    for mode in TimMode:
        prompt = TIM_SYSTEM_PROMPTS[mode]
        assert "Тебя зовут Вера" in prompt and "проектный менеджер" in prompt
        assert "женском роде" in prompt
        assert "Тим" not in prompt
    assert "Вера, проектный менеджер" in TRACKER_ROUTER_SYSTEM_PROMPT
