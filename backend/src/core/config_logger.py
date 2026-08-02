import logging.config

from src.core.settings import get_settings

_is_configured = False


def configure_logging() -> None:
    """Один раз настраивает логирование приложения из logging.ini."""
    global _is_configured
    if _is_configured:
        return
    settings = get_settings()
    logging.config.fileConfig(
        fname=settings.app.logging_config_path,
        disable_existing_loggers=False,
    )
    _is_configured = True
