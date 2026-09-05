import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pprint import pformat

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.endpoints.analytics import router as analytics_router
from src.api.v1.endpoints.api_tokens import router as api_tokens_router
from src.api.v1.endpoints.auth import router as auth_router
from src.api.v1.endpoints.calendar import router as calendar_router
from src.api.v1.endpoints.calendar_scenarios import router as calendar_scenarios_router
from src.api.v1.endpoints.dashboard import router as dashboard_router
from src.api.v1.endpoints.document_links import router as document_links_router
from src.api.v1.endpoints.documents import router as documents_router
from src.api.v1.endpoints.knowledge import router as knowledge_router
from src.api.v1.endpoints.milestones import router as milestones_router
from src.api.v1.endpoints.project_members import router as project_members_router
from src.api.v1.endpoints.project_stages import router as project_stages_router
from src.api.v1.endpoints.project_stickers import router as project_stickers_router
from src.api.v1.endpoints.projects import router as projects_router
from src.api.v1.endpoints.task_activity import router as task_activity_router
from src.api.v1.endpoints.task_attachments import router as task_attachments_router
from src.api.v1.endpoints.task_comments import router as task_comments_router
from src.api.v1.endpoints.task_dependencies import router as task_dependencies_router
from src.api.v1.endpoints.task_documents import router as task_documents_router
from src.api.v1.endpoints.tasks import router as tasks_router
from src.api.v1.endpoints.users import router as users_router
from src.api.v1.endpoints.wbs_nodes import router as wbs_nodes_router
from src.core.app_state import RUNTIME_STATE_KEY, SETTINGS_STATE_KEY
from src.core.config_logger import configure_logging
from src.core.settings import get_settings
from src.db.session import async_session_factory, engine
from src.exceptions.knowledge import KnowledgeProviderError
from src.knowledge.runtime import (
    build_knowledge_runtime,
    close_knowledge_runtime,
    create_http_client,
    create_qdrant_client,
)
from src.knowledge.worker import run_knowledge_worker
from src.mcp_server.server import build_mcp_app, mcp_server
from src.utils.check_db import check_db_connection

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, object]]:
    """Создаёт тяжёлые ресурсы при старте и освобождает их при остановке.

    Приложение — единственный владелец сетевых клиентов: они создаются
    здесь, отдаются graph-у зависимостей через состояние запроса и здесь же
    закрываются. Смонтированное MCP-приложение видит то же состояние,
    поэтому у обоих транспортов один набор клиентов, а не два.

    Args:
        app: Экземпляр FastAPI, жизненным циклом которого управляет функция.

    Yields:
        Состояние запроса с ресурсами приложения.
    """
    logger.info("🚀 Запуск приложения %s.", settings.app.app_name)
    async with async_session_factory() as db_session:
        await check_db_connection(db_session=db_session)

    http_client = create_http_client(settings)
    qdrant_client = create_qdrant_client(settings)
    runtime = build_knowledge_runtime(
        settings=settings,
        http_client=http_client,
        qdrant_client=qdrant_client,
    )
    worker_stop = asyncio.Event()
    worker_task: asyncio.Task | None = None
    if settings.knowledge.knowledge_enabled:
        try:
            await runtime.qdrant_client.backfill_payload_indexes()
        except KnowledgeProviderError:
            runtime.payload_indexes_backfill_pending = True
            logger.warning(
                "⚠️ Qdrant недоступен при старте; backfill payload-индексов отложен.",
                exc_info=True,
            )
        worker_task = asyncio.create_task(
            run_knowledge_worker(stop_event=worker_stop, settings=settings, runtime=runtime),
            name="project-knowledge-indexer",
        )
        logger.info("✅ Фоновый индексатор базы знаний запущен.")
    try:
        # Сессионный менеджер MCP обязан работать всё время жизни приложения:
        # смонтированное ASGI-приложение своего lifespan не получает.
        async with mcp_server.session_manager.run():
            logger.info("✅ MCP-сервер доступен на %s.", settings.app.mcp_path)
            logger.info("✅ Приложение успешно запущено.")
            yield {RUNTIME_STATE_KEY: runtime, SETTINGS_STATE_KEY: settings}
    finally:
        worker_stop.set()
        if worker_task is not None:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task
        await close_knowledge_runtime(runtime)
        await engine.dispose()
        logger.info("✅ Ресурсы приложения освобождены.")


app = FastAPI(
    title=settings.app.app_name,
    version=settings.app.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    # Сессия живёт в cookie, поэтому браузеру нужно разрешение слать её кросс-origin.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Преобразует ошибки Pydantic/FastAPI в единый ответ 422.

    Args:
        request: Исходный HTTP-запрос.
        exc: Ошибка валидации.

    Returns:
        JSON-ответ с деталями некорректных полей.
    """
    errors = exc.errors()
    logger.warning(
        "⚠️ Ошибка валидации %s %s. Детали:\n%s",
        request.method,
        request.url.path,
        pformat(errors),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(errors)},
    )


for api_router in (
    auth_router,
    users_router,
    api_tokens_router,
    dashboard_router,
    analytics_router,
    calendar_router,
    calendar_scenarios_router,
    milestones_router,
    projects_router,
    project_stickers_router,
    project_members_router,
    project_stages_router,
    tasks_router,
    wbs_nodes_router,
    documents_router,
    document_links_router,
    task_comments_router,
    task_dependencies_router,
    task_activity_router,
    task_attachments_router,
    task_documents_router,
    knowledge_router,
):
    app.include_router(api_router, prefix=settings.app.api_v1_prefix)


# MCP монтируется отдельным ASGI-приложением: его транспорт держит долгие
# соединения и не вписывается в контур обычных JSON-эндпоинтов.
mcp_app = build_mcp_app(settings=settings)
app.mount(settings.app.mcp_path, mcp_app)
