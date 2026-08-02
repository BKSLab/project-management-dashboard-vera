"""Опциональная загрузка документов и обязательная проверка базовой ИСР.

Запуск из backend после миграций:
    python scripts/seed_initial_data.py [путь_к_site_work_for_everyone]
"""

import asyncio
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config_logger import configure_logging  # noqa: E402
from src.db.session import async_session_factory  # noqa: E402
from src.dependencies.initial_data import create_initial_data_service  # noqa: E402
from src.repositories.documents import DocumentsRepository  # noqa: E402

configure_logging()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DOCS_DIR = PROJECT_ROOT.parent / "site_work_for_everyone"
PROJECT_DOCUMENT_OVERRIDES = {
    "DESIGN_GUIDE.md": PROJECT_ROOT / "docs" / "DESIGN_GUIDE.md",
}
DOCUMENT_CANDIDATES = (
    "README.md",
    "AGENT_VERA_ARCHITECTURE.md",
    "DESIGN_GUIDE.md",
    "BUGS.md",
    "BLOG_CHEATSHEET.md",
    "ADMIN_STATS_GUIDE.md",
    "FRONTEND_AUDIT_REPORT.md",
    "focus_management_best_practices_accessibility_guide.md",
    "BUG-001_FAVORITES_FIX_REPORT.md",
)
H1_RE = re.compile(r"^#\s+(.+)$")


def slugify(filename: str) -> str:
    """Преобразует имя файла документа в стабильный slug."""
    return filename.rsplit(".", 1)[0].lower().replace(" ", "_")


def extract_title(content: str, fallback: str) -> str:
    """Возвращает первый Markdown-заголовок или резервное имя файла."""
    for line in content.splitlines():
        match = H1_RE.match(line.strip())
        if match:
            return match.group(1).strip()
    return fallback


async def seed_documents(repository: DocumentsRepository, source_dir: Path) -> None:
    """Создаёт отсутствующие документы и синхронизирует проектные overrides."""
    for filename in DOCUMENT_CANDIDATES:
        file_path = PROJECT_DOCUMENT_OVERRIDES.get(filename, source_dir / filename)
        if not file_path.exists():
            logger.warning("⚠️ Файл документа не найден, пропуск: %s", file_path)
            continue

        content = file_path.read_text(encoding="utf-8")
        title = extract_title(content=content, fallback=filename)
        slug = slugify(filename)
        existing = await repository.get_by_slug(slug=slug)
        if existing is not None:
            if filename in PROJECT_DOCUMENT_OVERRIDES:
                await repository.update(
                    document=existing,
                    data={"title": title, "content_md": content},
                )
                logger.info("🔄 Документ %s синхронизирован.", slug)
            else:
                logger.info("✅ Документ %s уже существует.", slug)
            continue

        await repository.create(slug=slug, title=title, content_md=content)
        logger.info("➕ Документ %s создан.", slug)


async def main() -> None:
    """Загружает доступные документы и гарантирует готовность базовой ИСР."""
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE_DOCS_DIR
    logger.info("🚀 Запуск загрузки начальных данных. Документы: %s.", source_dir)
    async with async_session_factory() as session:
        await seed_documents(
            repository=DocumentsRepository(session),
            source_dir=source_dir,
        )
        initial_data_service = create_initial_data_service(session=session)
        await initial_data_service.ensure_loaded()
    logger.info("✅ Загрузка начальных данных завершена.")


if __name__ == "__main__":
    asyncio.run(main())
