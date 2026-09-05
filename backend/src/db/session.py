from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.settings import get_settings

settings = get_settings()

# Пределы пула заданы явно: при их отсутствии поведение под нагрузкой
# определяли бы умолчания SQLAlchemy, а не решение проекта. Формула общего
# числа соединений и основание значений — в docstring `DBSettings`.
engine = create_async_engine(
    url=settings.db.url_connect,
    pool_size=settings.db.pool_size,
    max_overflow=settings.db.pool_max_overflow,
    pool_timeout=settings.db.pool_timeout,
    pool_pre_ping=settings.db.pool_pre_ping,
    pool_recycle=settings.db.pool_recycle,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
