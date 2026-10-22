"""Запуск отдельного MCP: python -m src.mcp_server.worker."""

import uvicorn

from src.core.config_logger import configure_logging
from src.core.settings import get_settings
from src.db.session import async_session_factory, engine
from src.mcp_server.app import create_app


def run() -> int:
    configure_logging()
    settings = get_settings()
    app = create_app(settings=settings, session_factory=async_session_factory, engine=engine)
    uvicorn.run(app, host=settings.mcp.mcp_host, port=settings.mcp.mcp_port,
                log_config=None, workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
