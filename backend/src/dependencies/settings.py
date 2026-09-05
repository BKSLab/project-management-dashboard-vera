"""Доступ к настройкам приложения на уровне сборки графа зависимостей.

`get_settings()` вызывается здесь и в composition root, но не в сервисах:
сервис получает конкретные значения через конструктор и не знает, откуда
они взялись.
"""

from typing import Annotated

from fastapi import Depends

from src.core.settings import Settings, get_settings


def get_app_settings() -> Settings:
    """Возвращает настройки приложения для фабрик зависимостей."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
