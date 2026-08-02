"""Совместимая точка входа для команды ``hypercorn main:app``."""

from src.main import app

__all__ = ["app"]
