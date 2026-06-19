"""Идемпотентный сидинг начальных данных дашборда.

Запуск (из каталога backend, после `alembic upgrade head`):
    PYTHONPATH=. venv/Scripts/python.exe scripts/seed_initial_data.py [путь_к_site_work_for_everyone]
"""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config_logger import logger  # noqa: E402
from src.db.models.documents import Document  # noqa: E402
from src.db.models.kanban import KanbanStage, KanbanTask  # noqa: E402
from src.db.models.wbs import WbsItem, WbsRole  # noqa: E402
from src.db.session import async_session_factory  # noqa: E402
from src.repositories.documents import DocumentsRepository  # noqa: E402
from src.repositories.kanban import KanbanRepository  # noqa: E402
from src.repositories.wbs import WbsRepository  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DOCS_DIR = PROJECT_ROOT.parent / "site_work_for_everyone"
WBS_TXT_PATH = PROJECT_ROOT / "docs" / "AGENT_VERA_WBS.txt"

DOCUMENT_CANDIDATES = [
    "README.md",
    "AGENT_VERA_ARCHITECTURE.md",
    "DESIGN_GUIDE.md",
    "BUGS.md",
    "BLOG_CHEATSHEET.md",
    "ADMIN_STATS_GUIDE.md",
    "FRONTEND_AUDIT_REPORT.md",
    "focus_management_best_practices_accessibility_guide.md",
    "BUG-001_FAVORITES_FIX_REPORT.md",
]

DEFAULT_STAGES = [
    {"name": "Бэклог", "order_index": 0, "color": "#999999", "is_done_stage": False},
    {"name": "К выполнению", "order_index": 1, "color": "#3B82F6", "is_done_stage": False},
    {"name": "В работе", "order_index": 2, "color": "#F5B800", "is_done_stage": False},
    {"name": "На проверке", "order_index": 3, "color": "#A855F7", "is_done_stage": False},
    {"name": "Готово", "order_index": 4, "color": "#22C55E", "is_done_stage": True},
]

PHASE_RE = re.compile(r'^ФАЗА\s+\d+\.\s+(.+)$')
CROSS_CUTTING_RE = re.compile(r'^СКВОЗНЫЕ ЗАДАЧИ')
ITEM2_RE = re.compile(r'^(\d+\.\d+)\s+(.+?)(?:\s*\[([\w-]+)\])?\s*$')
ITEM3_RE = re.compile(r'^(\d+\.\d+\.\d+)\s+(.+?)\s*$')
H1_RE = re.compile(r'^#\s+(.+)$')


def slugify(filename: str) -> str:
    return filename.rsplit('.', 1)[0].lower().replace(' ', '_')


def extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        match = H1_RE.match(line.strip())
        if match:
            return match.group(1).strip()
    return fallback


async def seed_documents(documents_repository: DocumentsRepository, source_dir: Path) -> None:
    """Создаёт документы из набора .md-файлов, если их ещё нет в базе (проверка по slug)."""
    for filename in DOCUMENT_CANDIDATES:
        file_path = source_dir / filename
        if not file_path.exists():
            logger.warning("⚠️ Файл документа не найден, пропуск: %s", file_path)
            continue

        slug = slugify(filename)
        existing = await documents_repository.get_by_slug(slug=slug)
        if existing is not None:
            logger.info("ℹ️ Документ '%s' уже существует, пропуск.", slug)
            continue

        content = file_path.read_text(encoding='utf-8')
        title = extract_title(content, fallback=filename)
        await documents_repository.create(slug=slug, title=title, content_md=content)
        logger.info("✅ Документ '%s' создан.", slug)


async def seed_stages(kanban_repository: KanbanRepository) -> dict[str, int]:
    """Создаёт стандартные стадии канбана, если их ещё нет ни одной."""
    existing_stages = await kanban_repository.get_all_stages()
    if existing_stages:
        logger.info("ℹ️ Стадии канбана уже существуют, пропуск сидирования стадий.")
        return {stage.name: stage.id for stage in existing_stages}

    stages_by_name: dict[str, int] = {}
    for stage_data in DEFAULT_STAGES:
        stage = await kanban_repository.create_stage(data=stage_data)
        stages_by_name[stage.name] = stage.id
        logger.info("✅ Стадия '%s' создана.", stage.name)
    return stages_by_name


def parse_wbs(text: str) -> list[dict]:
    """Парсит AGENT_VERA_WBS.txt в плоский список узлов с указанием родителя по коду."""
    nodes: list[dict] = []
    phase_index = 0
    current_phase_code: str | None = None
    current_item2_code: str | None = None
    phase_order = 0
    item2_order = 0
    item3_order = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        phase_match = PHASE_RE.match(line)
        cross_match = CROSS_CUTTING_RE.match(line)
        if phase_match or cross_match:
            phase_index += 1
            current_phase_code = str(phase_index)
            current_item2_code = None
            item2_order = 0
            phase_name = phase_match.group(1) if phase_match else line
            nodes.append({
                "code": current_phase_code,
                "parent_code": None,
                "phase_name": phase_name,
                "title": phase_name,
                "role": None,
                "order_index": phase_order,
                "is_leaf": False,
            })
            phase_order += 1
            continue

        if raw_line.startswith('    ') and not raw_line.startswith('     '):
            # Уровень 3: "    1.1.1 Заголовок"
            item3_match = ITEM3_RE.match(line)
            if item3_match and current_item2_code:
                code, title = item3_match.groups()
                nodes.append({
                    "code": code,
                    "parent_code": current_item2_code,
                    "phase_name": None,
                    "title": title,
                    "role": None,
                    "order_index": item3_order,
                    "is_leaf": True,
                })
                item3_order += 1
            continue

        # Уровень 2: "1.1 Заголовок [Роль]"
        item2_match = ITEM2_RE.match(line)
        if item2_match and current_phase_code:
            code, title, role = item2_match.groups()
            if not re.match(r'^\d+\.\d+$', code):
                continue
            current_item2_code = code
            item3_order = 0
            nodes.append({
                "code": code,
                "parent_code": current_phase_code,
                "phase_name": None,
                "title": title.strip(),
                "role": role,
                "order_index": item2_order,
                "is_leaf": False,
            })
            item2_order += 1

    return nodes


ROLE_ALIASES = {
    "UX-R": WbsRole.UXR,
    "UX-D": WbsRole.UXD,
    "Backend": WbsRole.BE,
    "Frontend": WbsRole.FE,
    "Expert": WbsRole.EXPERT,
}


def resolve_role(raw_role: str | None) -> WbsRole | None:
    if raw_role is None:
        return None
    if raw_role in ROLE_ALIASES:
        return ROLE_ALIASES[raw_role]
    try:
        return WbsRole(raw_role)
    except ValueError:
        logger.warning("⚠️ Неизвестная роль ИСР: %s", raw_role)
        return None


async def seed_wbs(wbs_repository: WbsRepository, kanban_repository: KanbanRepository) -> None:
    """Парсит ИСР и создаёт дерево WbsItem + связанные KanbanTask для листьев."""
    if not WBS_TXT_PATH.exists():
        logger.warning("⚠️ Файл ИСР не найден: %s", WBS_TXT_PATH)
        return

    existing_items = await wbs_repository.get_all_items()
    code_to_id: dict[str, int] = {item.code: item.id for item in existing_items}
    leaf_codes_with_task = {item.code for item in existing_items if item.is_leaf and item.task is not None}

    stages = await kanban_repository.get_all_stages()
    backlog_stage = next((stage for stage in stages if stage.name == "Бэклог"), stages[0] if stages else None)
    if backlog_stage is None:
        logger.warning("⚠️ Нет стадий канбана, пропуск создания задач для листьев ИСР.")
        return

    text = WBS_TXT_PATH.read_text(encoding='utf-8')
    parsed_nodes = parse_wbs(text)

    for node in parsed_nodes:
        code = node["code"]
        if code in code_to_id:
            item_id = code_to_id[code]
        else:
            parent_id = code_to_id.get(node["parent_code"]) if node["parent_code"] else None
            item = await wbs_repository.create_item(data={
                "parent_id": parent_id,
                "code": code,
                "phase_name": node["phase_name"],
                "title": node["title"],
                "role": resolve_role(node["role"]),
                "order_index": node["order_index"],
                "is_leaf": node["is_leaf"],
            })
            code_to_id[code] = item.id
            item_id = item.id
            logger.info("✅ Узел ИСР '%s' создан.", code)

        if node["is_leaf"] and code not in leaf_codes_with_task:
            await kanban_repository.create_task(data={
                "wbs_item_id": item_id,
                "stage_id": backlog_stage.id,
                "title": node["title"],
                "position": float(node["order_index"]),
            })
            logger.info("✅ Задача канбана для ИСР '%s' создана.", code)


async def main() -> None:
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE_DOCS_DIR
    logger.info("🚀 Запуск сидирования начальных данных...")

    async with async_session_factory() as session:
        documents_repository = DocumentsRepository(session)
        kanban_repository = KanbanRepository(session)
        wbs_repository = WbsRepository(session)

        await seed_documents(documents_repository=documents_repository, source_dir=source_dir)
        await seed_stages(kanban_repository=kanban_repository)
        await seed_wbs(wbs_repository=wbs_repository, kanban_repository=kanban_repository)

    logger.info("✅ Сидирование завершено.")


if __name__ == "__main__":
    asyncio.run(main())
