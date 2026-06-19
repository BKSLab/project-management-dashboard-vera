from fastapi import FastAPI, Request, status
from fastapi.concurrency import asynccontextmanager
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.document_links import router as document_links_router
from src.api.documents import router as documents_router
from src.api.kanban import router as kanban_router
from src.api.wbs import router as wbs_router
from src.core.config_logger import logger
from src.core.settings import get_settings
from src.db.session import async_session_factory
from src.utils.check_db import check_db_connection

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Функция управления жизненным циклом приложения."""
    logger.info("🚀 Запуск приложения...")
    async with async_session_factory() as db_session:
        await check_db_connection(db_session=db_session)
    logger.info("✅ Приложение успешно запущено.")
    yield
    logger.info("🛑 Приложение останавливается...")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Перехватывает ошибки валидации Pydantic и возвращает стандартный ответ 422."""
    logger.warning(
        "Ошибка валидации для запроса: %s %s. Детали: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )


app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(kanban_router, prefix="/api/kanban", tags=["kanban"])
app.include_router(wbs_router, prefix="/api/wbs", tags=["wbs"])
app.include_router(document_links_router, prefix="/api/document-links", tags=["document-links"])
