import logging
import logging.config

from src.core.settings import get_settings

settings = get_settings()

logging.config.fileConfig(fname=settings.app.logging_config_path, disable_existing_loggers=False)

logger = logging.getLogger('project_dashboard')
