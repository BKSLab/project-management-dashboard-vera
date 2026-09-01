from io import BytesIO

import docx

from src.knowledge.chunking import chunk_markdown, chunk_text
from src.knowledge.extract import extract_indexable_text


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


def test_extracts_docx_paragraphs_and_table() -> None:
    document = docx.Document()
    document.add_paragraph("Описание проекта")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Риск"
    table.cell(0, 1).text = "Срок"
    stream = BytesIO()
    document.save(stream)

    extracted = extract_indexable_text("паспорт.docx", stream.getvalue())

    assert extracted is not None
    assert "Описание проекта" in extracted
    assert "Риск | Срок" in extracted


def test_skips_non_indexable_attachment() -> None:
    assert extract_indexable_text("макет.png", b"binary") is None
