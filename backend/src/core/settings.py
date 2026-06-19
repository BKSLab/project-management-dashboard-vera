import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SettingsBase(BaseSettings):
    """Базовый класс для настроек приложения."""
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, '.env'),
        extra='ignore'
    )


class AppSettings(SettingsBase):
    """Класс настроек для приложения."""
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    logging_config_path: Path = BASE_DIR / "logging.ini"


class DBSettings(SettingsBase):
    """Класс настроек для работы с БД."""
    postgres_host: SecretStr
    postgres_port: int = 5432
    postgres_user: SecretStr
    postgres_password: SecretStr
    postgres_name: SecretStr

    @property
    def url_connect(self) -> str:
        return (
            f'postgresql+asyncpg://{self.postgres_user.get_secret_value()}:'
            f'{self.postgres_password.get_secret_value()}@'
            f'{self.postgres_host.get_secret_value()}:'
            f'{self.postgres_port}/'
            f'{self.postgres_name.get_secret_value()}'
        )


class Settings(BaseSettings):
    """Общий класс настроек приложения."""
    db: DBSettings = Field(default_factory=DBSettings)
    app: AppSettings = Field(default_factory=AppSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
