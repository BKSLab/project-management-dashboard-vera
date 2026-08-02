import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pprint import pformat

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.endpoints.document_links import router as document_links_router
from src.api.v1.endpoints.documents import router as documents_router
from src.api.v1.endpoints.kanban_stages import router as kanban_stages_router
from src.api.v1.endpoints.kanban_tasks import router as kanban_tasks_router
from src.api.v1.endpoints.task_activity import router as task_activity_router
from src.api.v1.endpoints.task_comments import router as task_comments_router
from src.api.v1.endpoints.wbs import router as wbs_router
from src.core.config_logger import configure_logging
from src.core.settings import get_settings
from src.db.session import async_session_factory, engine
from src.dependencies.initial_data import create_initial_data_service
from src.utils.check_db import check_db_connection

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Проверяет критичные ресурсы при старте и освобождает их при остановке.

    Args:
        app: Экземпляр FastAPI, жизненным циклом которого управляет функция.

    Yields:
        Управление запущенному приложению после успешных стартовых проверок.
    """
    logger.info("🚀 Запуск приложения %s.", settings.app.app_name)
    async with async_session_factory() as db_session:
        await check_db_connection(db_session=db_session)
        initial_data_service = create_initial_data_service(session=db_session)
        await initial_data_service.ensure_loaded()
    logger.info("✅ Приложение успешно запущено.")
    yield
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
    documents_router,
    document_links_router,
    kanban_stages_router,
    kanban_tasks_router,
    task_comments_router,
    task_activity_router,
    wbs_router,
):
    app.include_router(api_router, prefix=settings.app.api_v1_prefix)
