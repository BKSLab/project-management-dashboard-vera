import re
from dataclasses import dataclass

MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class TextChunk:
    """Смысловой фрагмент текста для одного Qdrant point."""

    index: int
    heading: str | None
    text: str


def chunk_markdown(
    content: str,
    *,
    target_chars: int,
    overlap_chars: int,
) -> list[TextChunk]:
    """Делит Markdown сначала по заголовкам, затем по абзацам."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    sections: list[tuple[str | None, str]] = []
    heading: str | None = None
    lines: list[str] = []
    for line in normalized.splitlines():
        match = MARKDOWN_HEADING.match(line)
        if match:
            if "\n".join(lines).strip():
                sections.append((heading, "\n".join(lines).strip()))
            heading = match.group(1).strip()
            lines = []
        else:
            lines.append(line)
    if "\n".join(lines).strip() or not sections:
        sections.append((heading, "\n".join(lines).strip()))

    result: list[TextChunk] = []
    for section_heading, section_text in sections:
        for part in chunk_text(
            section_text,
            target_chars=target_chars,
            overlap_chars=overlap_chars,
        ):
            result.append(TextChunk(index=len(result), heading=section_heading, text=part))
    return result


def chunk_text(text: str, *, target_chars: int, overlap_chars: int) -> list[str]:
    """Режет обычный текст по абзацам с небольшим словесным overlap."""
    normalized = re.sub(r"[ \t]+", " ", text).strip()
    if not normalized:
        return []
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n|(?<=\.)\s*\n", normalized) if part.strip()
    ]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = _split_oversized(paragraph, target_chars)
        for piece in pieces:
            candidate = f"{current}\n\n{piece}".strip() if current else piece
            if current and len(candidate) > target_chars:
                chunks.append(current)
                overlap = _tail(current, overlap_chars)
                current = f"{overlap}\n\n{piece}".strip() if overlap else piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _split_oversized(text: str, target_chars: int) -> list[str]:
    if len(text) <= target_chars:
        return [text]
    words = text.split()
    result: list[str] = []
    current: list[str] = []
    current_length = 0
    for word in words:
        projected = current_length + len(word) + (1 if current else 0)
        if current and projected > target_chars:
            result.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length = projected
    if current:
        result.append(" ".join(current))
    return result


def _tail(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text if limit > 0 else ""
    tail = text[-limit:]
    separator = tail.find(" ")
    return tail[separator + 1 :] if separator >= 0 else tail
