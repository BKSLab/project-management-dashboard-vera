from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from src.dependencies.db_session import DbSessionDep
from src.repositories.task_attention import TaskAttentionRepository
from src.repositories.unit_of_work import UnitOfWork
from src.services.task_attention import TaskAttentionService


def get_task_attention_service(session: DbSessionDep) -> TaskAttentionService:
    """HTTP-сервис; сессия не передаётся долгоживущему маршруту."""
    return TaskAttentionService(TaskAttentionRepository(session), UnitOfWork(session))


TaskAttentionServiceDep = Annotated[TaskAttentionService, Depends(get_task_attention_service)]


def get_task_attention_runtime(connection: HTTPConnection):
    """Ресурс lifespan без request-scoped сессии."""
    return connection.state.task_attention_runtime


TaskAttentionRuntimeDep = Annotated[object, Depends(get_task_attention_runtime)]


def build_task_attention_runtime(*, settings, session_factory):
    """Собирает короткие области, закрываемые до ожидания событий."""
    import asyncpg

    from src.mcp_server.services import build_auth_service
    from src.realtime.task_attention import TaskAttentionRuntime

    async def authenticate(**credentials):
        async with session_factory() as session:
            auth = build_auth_service(session, settings)
            return await auth.resolve_principal(**credentials)

    async def snapshot(user_id):
        async with session_factory() as session:
            service = TaskAttentionService(TaskAttentionRepository(session), UnitOfWork(session))
            return await service.snapshot(user_id)

    async def connect():
        db = settings.db
        return await asyncpg.connect(
            host=db.postgres_host,
            port=db.postgres_port,
            user=db.postgres_user,
            password=db.postgres_password.get_secret_value(),
            database=db.postgres_name,
            timeout=settings.task_attention.attention_connect_timeout,
            command_timeout=settings.task_attention.attention_connect_timeout,
        )

    return TaskAttentionRuntime(
        connect=connect,
        authenticate=authenticate,
        snapshot=snapshot,
        config=settings.task_attention,
    )
