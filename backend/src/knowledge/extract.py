from io import BytesIO
from pathlib import Path

import docx
import pdfplumber

INDEXABLE_EXTENSIONS = frozenset({".pdf", ".docx", ".md", ".txt"})
MAX_PDF_PAGES = 2000


def extract_indexable_text(filename: str, content: bytes) -> str | None:
    """Извлекает текст PDF/DOCX/Markdown/TXT; остальные типы пропускает."""
    suffix = Path(filename).suffix.lower()
    if suffix not in INDEXABLE_EXTENSIONS:
        return None
    if suffix in {".md", ".txt"}:
        return content.decode("utf-8", errors="replace").strip()
    if suffix == ".pdf":
        with pdfplumber.open(BytesIO(content)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise ValueError(f"PDF содержит больше {MAX_PDF_PAGES} страниц.")
            return "\n\n".join(page.extract_text() or "" for page in pdf.pages).strip()
    return _extract_docx(content).strip()


def _extract_docx(content: bytes) -> str:
    """Извлекает параграфы и таблицы DOCX в порядке XML-блоков."""
    document = docx.Document(BytesIO(content))
    blocks: list[str] = []
    for block in document.element.body.iterchildren():
        tag = block.tag.split("}")[-1]
        if tag == "p":
            paragraph = docx.text.paragraph.Paragraph(block, document)
            text = paragraph.text.strip()
            if text:
                blocks.append(text)
        elif tag == "tbl":
            table = docx.table.Table(block, document)
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    blocks.append(" | ".join(cells))
    return "\n".join(blocks)
