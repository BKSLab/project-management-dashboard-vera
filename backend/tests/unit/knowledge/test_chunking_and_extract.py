from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import docx
import pytest
import xlwt
from openpyxl import Workbook
from PIL import Image

from src.knowledge.chunking import chunk_markdown, chunk_text
from src.knowledge.extract import extract_indexable_text


def build_workbook_bytes(build) -> bytes:
    """Собирает книгу в память, применив к листу переданную настройку."""
    workbook = Workbook()
    build(workbook.active)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def build_legacy_workbook_bytes(rows: list[list], title: str = "Смета") -> bytes:
    """Собирает книгу формата .xls, которого openpyxl не умеет записывать."""
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet(title)
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            if value is not None:
                sheet.write(row_index, column_index, value)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def build_image_bytes(color: str = "white", size: tuple[int, int] = (64, 32)) -> bytes:
    """Собирает минимальный PNG для проверок распознавания."""
    stream = BytesIO()
    Image.new("RGB", size, color).save(stream, format="PNG")
    return stream.getvalue()


def test_chunk_markdown_keeps_section_headings() -> None:
    content = "# Контекст\nПервый раздел.\n\n## Решение\nВторой раздел."

    chunks = chunk_markdown(content, target_chars=100, overlap_chars=10)

    assert [chunk.heading for chunk in chunks] == ["Контекст", "Решение"]
    assert [chunk.index for chunk in chunks] == [0, 1]
    assert chunks[1].text == "Второй раздел."


def test_chunk_text_splits_large_content_deterministically() -> None:
    text = " ".join(f"слово-{index}" for index in range(60))

    first = chunk_text(text, target_chars=100, overlap_chars=20)
    second = chunk_text(text, target_chars=100, overlap_chars=20)

    assert first == second
    assert len(first) > 1
    assert all(chunk.strip() for chunk in first)


async def test_extracts_docx_paragraphs_and_table() -> None:
    document = docx.Document()
    document.add_paragraph("Описание проекта")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Риск"
    table.cell(0, 1).text = "Срок"
    stream = BytesIO()
    document.save(stream)

    extracted = await extract_indexable_text("паспорт.docx", stream.getvalue())

    assert extracted is not None
    assert "Описание проекта" in extracted
    assert "Риск | Срок" in extracted


async def test_skips_unsupported_attachment() -> None:
    assert await extract_indexable_text("архив.zip", b"binary") is None


async def test_extracts_csv_in_legacy_encoding() -> None:
    content = "этап;срок\nпроектирование;март".encode("cp1251")

    extracted = await extract_indexable_text("план.csv", content)

    assert extracted == "этап;срок\nпроектирование;март"


async def test_extracts_xlsx_rows_as_labelled_values() -> None:
    def build(sheet):
        sheet.title = "Смета"
        sheet.append(["Работа", "Стоимость"])
        sheet.append(["Монтаж", 1500])

    extracted = await extract_indexable_text("смета.xlsx", build_workbook_bytes(build))

    assert extracted == "Лист: Смета\nРабота: Монтаж, Стоимость: 1500"


async def test_xlsx_skips_hidden_rows_and_expands_merged_cells() -> None:
    def build(sheet):
        sheet.title = "Этапы"
        sheet.append(["Этап", "Задача"])
        sheet.append(["Подготовка", "Смета"])
        sheet.append([None, "График"])
        sheet.append(["Черновик", "Не считать"])
        sheet.merge_cells("A2:A3")
        sheet.row_dimensions[4].hidden = True

    extracted = await extract_indexable_text("этапы.xlsx", build_workbook_bytes(build))

    assert extracted == (
        "Лист: Этапы\nЭтап: Подготовка, Задача: Смета\nЭтап: Подготовка, Задача: График"
    )


async def test_xlsx_without_data_rows_yields_empty_text() -> None:
    def build(sheet):
        sheet.append(["Работа", "Стоимость"])

    extracted = await extract_indexable_text("пусто.xlsx", build_workbook_bytes(build))

    assert extracted == ""


async def test_recognises_image_through_vision_model() -> None:
    vision = SimpleNamespace(extract_text=AsyncMock(return_value="Схема электрощита"))

    extracted = await extract_indexable_text(
        "схема.png",
        build_image_bytes(),
        vision_client=vision,
    )

    assert extracted == "Схема электрощита"
    assert vision.extract_text.await_args.kwargs["image_base64"]


async def test_skips_image_when_vision_disabled() -> None:
    assert await extract_indexable_text("схема.png", build_image_bytes()) is None


async def test_truncates_text_above_configured_limit() -> None:
    content = ("строка " * 100).encode("utf-8")

    extracted = await extract_indexable_text("лог.log", content, max_chars=20)

    assert extracted is not None
    assert len(extracted) == 20


async def test_extracts_legacy_xls_workbook() -> None:
    content = build_legacy_workbook_bytes([["Работа", "Стоимость"], ["Монтаж", 1500]])

    extracted = await extract_indexable_text("смета.xls", content)

    assert extracted == "Лист: Смета\nРабота: Монтаж, Стоимость: 1500"


async def test_legacy_xls_fills_gaps_from_previous_row() -> None:
    content = build_legacy_workbook_bytes(
        [["Этап", "Задача"], ["Подготовка", "Смета"], [None, "График"]],
        title="Этапы",
    )

    extracted = await extract_indexable_text("этапы.xls", content)

    assert extracted == (
        "Лист: Этапы\nЭтап: Подготовка, Задача: Смета\nЭтап: Подготовка, Задача: График"
    )


async def test_corrupted_workbook_raises_value_error() -> None:
    with pytest.raises(ValueError):
        await extract_indexable_text("битая.xlsx", b"not a workbook at all")


async def test_xlsx_hidden_rows_align_when_table_starts_below_first_row() -> None:
    def build(sheet):
        sheet.title = "Реестр"
        sheet["A4"] = "Позиция"
        sheet["A5"] = "Кабель"
        sheet["A6"] = "Черновик"
        sheet.row_dimensions[6].hidden = True

    extracted = await extract_indexable_text("реестр.xlsx", build_workbook_bytes(build))

    assert extracted == "Лист: Реестр\nПозиция: Кабель"
