import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def check_db_connection(db_session: AsyncSession) -> bool:
    """Проверяет доступность БД и выполнение простого запроса."""
    try:
        await db_session.execute(text("SELECT 1"))
        logger.info("🗄️ Подключение к БД успешно проверено.")
    except Exception as error:
        logger.error("❌ Ошибка подключения к БД: %s", error, exc_info=True)
        raise RuntimeError('Database connection test failed') from error
