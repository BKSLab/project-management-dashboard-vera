"""Производственный календарь РФ: отклонения от обычной пятидневки.

Источники (сверено 28.09.2026 по производственным календарям КонсультантПлюс,
consultant.ru/law/ref/calendar/proizvodstvennye/<год>/):

- ст. 112 ТК РФ — нерабочие праздничные дни и перенос выходного,
  совпавшего с праздником, на следующий рабочий день (кроме январских);
- ст. 95 ТК РФ — предпраздничный день короче на час;
- 2025 — Постановление Правительства РФ от 04.10.2024 № 1335;
- 2026 — Постановление Правительства РФ от 24.09.2025 № 1466;
- 2027 — Постановление Правительства РФ от 17.09.2026 № 1187.

Каждый год проверен тестом по числу рабочих дней при пятидневке (247 во
всех трёх годах). Новый год добавляется только по опубликованному
постановлению: неверные даты хуже, чем ``known=false``.

Обычные субботы и воскресенья не перечисляются. Коды:
``HOLIDAY`` — праздник (в том числе выпавший на выходной), ``DAY_OFF`` —
будний день стал выходным, ``WORKING_DAY`` — выходной стал рабочим,
``SHORT_DAY`` — рабочий день на час короче (на субботе — это рабочая суббота).
"""

from datetime import date

NEW_YEAR = "Новогодние каникулы"
CHRISTMAS = "Рождество Христово"
DEFENDER = "День защитника Отечества"
WOMEN = "Международный женский день"
LABOUR = "Праздник Весны и Труда"
VICTORY = "День Победы"
RUSSIA = "День России"
UNITY = "День народного единства"
TRANSFER = "Перенесённый выходной"
SHORT = "Сокращённый предпраздничный день"
SHORT_WORKING_SATURDAY = "Рабочая суббота, сокращённый день"


def _statutory_holidays(year: int) -> list[tuple[date, str, str]]:
    """Нерабочие праздничные дни ст. 112 ТК РФ — одинаковы каждый год."""
    days = [(date(year, 1, day), "HOLIDAY", NEW_YEAR) for day in (1, 2, 3, 4, 5, 6, 8)]
    days += [
        (date(year, 1, 7), "HOLIDAY", CHRISTMAS),
        (date(year, 2, 23), "HOLIDAY", DEFENDER),
        (date(year, 3, 8), "HOLIDAY", WOMEN),
        (date(year, 5, 1), "HOLIDAY", LABOUR),
        (date(year, 5, 9), "HOLIDAY", VICTORY),
        (date(year, 6, 12), "HOLIDAY", RUSSIA),
        (date(year, 11, 4), "HOLIDAY", UNITY),
    ]
    return days


SOURCES: dict[int, str] = {
    2025: "Постановление Правительства РФ от 04.10.2024 № 1335",
    2026: "Постановление Правительства РФ от 24.09.2025 № 1466",
    2027: "Постановление Правительства РФ от 17.09.2026 № 1187",
}

# Отклонения сверх праздников ст. 112: переносы и сокращённые дни.
_ADJUSTMENTS: dict[int, list[tuple[date, str, str]]] = {
    2025: [
        # Переносы: 4 января → 2 мая, 5 января → 31 декабря, 23 февраля → 8 мая,
        # 8 марта → 13 июня, 1 ноября (суббота) → 3 ноября.
        (date(2025, 5, 2), "DAY_OFF", TRANSFER),
        (date(2025, 5, 8), "DAY_OFF", TRANSFER),
        (date(2025, 6, 13), "DAY_OFF", TRANSFER),
        (date(2025, 11, 3), "DAY_OFF", TRANSFER),
        (date(2025, 12, 31), "DAY_OFF", TRANSFER),
        (date(2025, 3, 7), "SHORT_DAY", SHORT),
        (date(2025, 4, 30), "SHORT_DAY", SHORT),
        (date(2025, 6, 11), "SHORT_DAY", SHORT),
        (date(2025, 11, 1), "SHORT_DAY", SHORT_WORKING_SATURDAY),
    ],
    2026: [
        # Переносы: 3 января → 9 января, 4 января → 31 декабря; по ст. 112 —
        # 8 марта (вс) → 9 марта, 9 мая (сб) → 11 мая.
        (date(2026, 1, 9), "DAY_OFF", TRANSFER),
        (date(2026, 3, 9), "DAY_OFF", TRANSFER),
        (date(2026, 5, 11), "DAY_OFF", TRANSFER),
        (date(2026, 12, 31), "DAY_OFF", TRANSFER),
        (date(2026, 4, 30), "SHORT_DAY", SHORT),
        (date(2026, 5, 8), "SHORT_DAY", SHORT),
        (date(2026, 6, 11), "SHORT_DAY", SHORT),
        (date(2026, 11, 3), "SHORT_DAY", SHORT),
    ],
    2027: [
        # Переносы: 2 января → 5 ноября, 3 января → 31 декабря, 20 февраля (сб) →
        # 22 февраля; по ст. 112 — 1 мая (сб) → 3 мая, 9 мая (вс) → 10 мая,
        # 12 июня (сб) → 14 июня.
        (date(2027, 2, 22), "DAY_OFF", TRANSFER),
        (date(2027, 5, 3), "DAY_OFF", TRANSFER),
        (date(2027, 5, 10), "DAY_OFF", TRANSFER),
        (date(2027, 6, 14), "DAY_OFF", TRANSFER),
        (date(2027, 11, 5), "DAY_OFF", TRANSFER),
        (date(2027, 12, 31), "DAY_OFF", TRANSFER),
        (date(2027, 2, 20), "SHORT_DAY", SHORT_WORKING_SATURDAY),
        (date(2027, 4, 30), "SHORT_DAY", SHORT),
        (date(2027, 6, 11), "SHORT_DAY", SHORT),
        (date(2027, 11, 3), "SHORT_DAY", SHORT),
    ],
}


def holiday_days(year: int) -> list[tuple[date, str, str]] | None:
    """Возвращает отклонения года, отсортированные по дате.

    Args:
        year: Календарный год.

    Returns:
        Кортежи ``(дата, код, подпись)`` либо ``None``, если данных на год нет.
    """
    adjustments = _ADJUSTMENTS.get(year)
    if adjustments is None:
        return None
    return sorted([*_statutory_holidays(year), *adjustments], key=lambda item: item[0])
