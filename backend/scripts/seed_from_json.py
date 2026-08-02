"""Проверка и одноразовая загрузка стадий канбана и базовой ИСР из JSON."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config_logger import configure_logging  # noqa: E402
from src.db.session import async_session_factory  # noqa: E402
from src.dependencies.initial_data import create_initial_data_service  # noqa: E402

configure_logging()
logger = logging.getLogger(__name__)


async def main() -> None:
    """Гарантирует готовность начальных данных перед запуском приложения."""
    logger.info("🚀 Проверка начальных данных ИСР.")
    async with async_session_factory() as session:
        service = create_initial_data_service(session=session)
        await service.ensure_loaded()
    logger.info("✅ Проверка начальных данных завершена.")


if __name__ == "__main__":
    asyncio.run(main())
