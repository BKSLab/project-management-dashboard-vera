"""Производственный календарь РФ и сборка iCalendar."""

from datetime import UTC, date, datetime, timedelta

from src.services.personal_calendar import PersonalCalendarService
from src.utils.holidays_ru import SOURCES, holiday_days
from src.utils.ics import IcsEvent, escape_text, fold_line, render_calendar

# Число рабочих дней по производственным календарям.
EXPECTED = {2025: 247, 2026: 247, 2027: 247}


def test_every_known_year_matches_official_working_day_count() -> None:
    """Данные года сходятся с официальным числом рабочих дней, а дни не повторяются."""
    for year, expected in EXPECTED.items():
        days = holiday_days(year)
        kinds = {day: kind for day, kind, _ in days}
        assert len(kinds) == len(days), f"{year}: дата указана дважды"
        assert all(day.year == year for day in kinds), year
        working = 0
        current = date(year, 1, 1)
        while current.year == year:
            kind = kinds.get(current)
            weekend = current.weekday() >= 5
            is_working = (
                kind in ("WORKING_DAY", "SHORT_DAY")
                if weekend
                else kind not in ("HOLIDAY", "DAY_OFF")
            )
            working += is_working
            current += timedelta(days=1)
        assert working == expected, year
    assert set(SOURCES) == set(EXPECTED)
    assert holiday_days(2031) is None
    unknown = PersonalCalendarService.get_holidays(2031)
    assert (unknown.known, unknown.days) == (False, [])


def test_ics_escapes_text_and_folds_long_lines_by_octets() -> None:
    """Спецсимволы экранируются, длинная кириллица переносится без разрыва символа."""
    assert escape_text("a;b,c\\d\ne") == "a\\;b\\,c\\\\d\\ne"
    line = "SUMMARY:" + "Ж" * 100
    folded = fold_line(line)
    parts = folded.split("\r\n ")
    assert "".join(parts) == line
    assert all(len(part.encode("utf-8")) <= 75 for part in parts)

    body = render_calendar(
        name="Мой",
        events=[
            IcsEvent(
                uid="task-1@t",
                summary="PROJ-1 Задача",
                date_from=date(2026, 12, 31),
                date_to=date(2026, 12, 31),
                stamp=datetime(2026, 9, 28, 10, 0, tzinfo=UTC),
            )
        ],
    )
    assert "DTSTART;VALUE=DATE:20261231\r\nDTEND;VALUE=DATE:20270101\r\n" in body
    assert "DTSTAMP:20260928T100000Z" in body
    assert all(line for line in body.split("\r\n")[:-1])
