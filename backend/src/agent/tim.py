"""Вера — проектный менеджер и правила обращения в проектном чате."""

from enum import StrEnum

TIM_NAME = "Вера"
"""Имя агента для людей и для самой модели; обращение к нему — просто «Вера»."""
_ADDRESS = "вера"
# Разделители после обращения, которые не несут смысла вопроса: «Вера, …», «Вера: …».
_ADDRESS_TAIL = " \t\r\n,.:;!?-—–"


class TimMode(StrEnum):
    """Где Вера отвечает: от этого зависят данные, инструменты и секция промпта."""

    PROJECT_CHAT = "project_chat"
    """Общий чат проекта: ответ видит вся команда, только данные этого проекта."""
    WIDGET_PROJECT = "widget_project"
    """Личный виджет, страница указывает на проект: его данные плюс личные действия."""
    WIDGET_PERSONAL = "widget_personal"
    """Личный виджет без проекта на странице: мои задачи, разовые, поиск."""


ALL_MODES = frozenset(TimMode)
PROJECT_MODES = frozenset({TimMode.PROJECT_CHAT, TimMode.WIDGET_PROJECT})
WIDGET_MODES = frozenset({TimMode.WIDGET_PROJECT, TimMode.WIDGET_PERSONAL})


def is_addressed_to_tim(text: str | None) -> bool:
    """Адресовано ли сообщение чата Вере.

    Args:
        text: Текст сообщения как его отправил участник.

    Returns:
        True для «Вера, что горит?», «ВЕРА перенеси срок», «вера»; False для
        «Веранда», «Вероника», «коллеги, Вера сказала» и старого «Тим, …».
    """
    normalized = (text or "").strip().lower()
    if not normalized.startswith(_ADDRESS):
        return False
    rest = normalized[len(_ADDRESS) :]
    return not rest or not rest[0].isalnum()


def strip_address(text: str) -> str:
    """Убирает обращение «Вера» и разделители из начала вопроса.

    Пустой остаток — исходный текст.
    """
    stripped = text.strip()
    if not is_addressed_to_tim(stripped):
        return stripped
    rest = stripped[len(_ADDRESS) :]
    rest = rest.lstrip(_ADDRESS_TAIL).strip()
    return rest or stripped
