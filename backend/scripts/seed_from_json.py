"""Идемпотентный сидинг стадий канбана и дерева ИСР из JSON-снэпшота при старте контейнера.

В отличие от seed_initial_data.py (парсит docs/AGENT_VERA_WBS.txt и сидирует документы
из соседнего репозитория site_work_for_everyone — недоступного на сервере), этот скрипт
самодостаточен: всё, что ему нужно, лежит внутри backend/scripts/data/wbs_seed.json,
который попадает в образ через `COPY . .` в Dockerfile.

Безопасно запускать на каждом старте контейнера: если в БД уже есть хотя бы один узел
ИСР — скрипт ничего не делает.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config_logger import logger  # noqa: E402
from src.db.models.wbs import WbsRole  # noqa: E402
from src.db.session import async_session_factory  # noqa: E402
from src.repositories.kanban import KanbanRepository  # noqa: E402
from src.repositories.wbs import WbsRepository  # noqa: E402

DATA_PATH = Path(__file__).resolve().parent / "data" / "wbs_seed.json"

DEFAULT_STAGES = [
    {"name": "Бэклог", "order_index": 0, "color": "#999999", "is_done_stage": False},
    {"name": "К выполнению", "order_index": 1, "color": "#3B82F6", "is_done_stage": False},
    {"name": "В работе", "order_index": 2, "color": "#F5B800", "is_done_stage": False},
    {"name": "На проверке", "order_index": 3, "color": "#A855F7", "is_done_stage": False},
    {"name": "Готово", "order_index": 4, "color": "#22C55E", "is_done_stage": True},
]


async def seed_stages(kanban_repository: KanbanRepository) -> dict[str, int]:
    existing_stages = await kanban_repository.get_all_stages()
    if existing_stages:
        return {stage.name: stage.id for stage in existing_stages}

    stages_by_name: dict[str, int] = {}
    for stage_data in DEFAULT_STAGES:
        stage = await kanban_repository.create_stage(data=stage_data)
        stages_by_name[stage.name] = stage.id
        logger.info("✅ Стадия '%s' создана.", stage.name)
    return stages_by_name


def resolve_role(raw_role: str | None) -> WbsRole | None:
    if raw_role is None:
        return None
    try:
        return WbsRole(raw_role)
    except ValueError:
        logger.warning("⚠️ Неизвестная роль ИСР: %s", raw_role)
        return None


async def seed_wbs(wbs_repository: WbsRepository, kanban_repository: KanbanRepository) -> None:
    existing_items = await wbs_repository.get_all_items()
    if existing_items:
        logger.info("ℹ️ ИСР уже загружена (%d узлов), пропуск сидинга из JSON.", len(existing_items))
        return

    if not DATA_PATH.exists():
        logger.warning("⚠️ Файл снэпшота ИСР не найден: %s", DATA_PATH)
        return

    nodes = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    stages_by_name = await seed_stages(kanban_repository)
    backlog_stage_id = stages_by_name.get("Бэклог")
    if backlog_stage_id is None:
        logger.warning("⚠️ Нет стадии «Бэклог», пропуск создания задач для листьев ИСР.")
        return

    code_to_id: dict[str, int] = {}
    for node in nodes:
        parent_id = code_to_id.get(node["parent_code"]) if node["parent_code"] else None
        item = await wbs_repository.create_item(data={
            "parent_id": parent_id,
            "code": node["code"],
            "phase_name": node["phase_name"],
            "title": node["title"],
            "role": resolve_role(node["role"]),
            "order_index": node["order_index"],
            "is_leaf": node["is_leaf"],
        })
        code_to_id[node["code"]] = item.id

        if node["is_leaf"]:
            await kanban_repository.create_task(data={
                "wbs_item_id": item.id,
                "stage_id": backlog_stage_id,
                "title": node["title"],
                "position": float(node["order_index"]),
            })

    logger.info("✅ ИСР загружена из JSON: %d узлов.", len(nodes))


async def main() -> None:
    logger.info("🚀 Проверка начальных данных ИСР...")
    async with async_session_factory() as session:
        kanban_repository = KanbanRepository(session)
        wbs_repository = WbsRepository(session)
        await seed_wbs(wbs_repository=wbs_repository, kanban_repository=kanban_repository)
    logger.info("✅ Проверка завершена.")


if __name__ == "__main__":
    asyncio.run(main())
