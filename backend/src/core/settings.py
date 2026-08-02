from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SettingsBase(BaseSettings):
    """Базовые правила чтения настроек из окружения и локального .env."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )


class AppSettings(SettingsBase):
    """Настройки HTTP-приложения и его инфраструктуры."""

    app_name: str = "Project Management Dashboard Vera"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    logging_config_path: Path = BASE_DIR / "logging.ini"
    uploads_path: Path = BASE_DIR / "uploads"


class DBSettings(SettingsBase):
    """Настройки подключения к PostgreSQL."""

    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: SecretStr
    postgres_name: str

    @property
    def url_connect(self) -> str:
        """Возвращает DSN асинхронного драйвера PostgreSQL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_name}"
        )


class Settings(BaseSettings):
    """Агрегатор настроек приложения по доменам."""

    db: DBSettings = Field(default_factory=DBSettings)
    app: AppSettings = Field(default_factory=AppSettings)


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный кэшированный экземпляр настроек."""
    return Settings()
