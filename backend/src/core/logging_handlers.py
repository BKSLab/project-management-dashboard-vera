import logging
import sys


class Utf8ConsoleHandler(logging.StreamHandler):
    """Выводит Unicode-логи в stdout без зависимости от кодовой страницы Windows."""

    def __init__(self) -> None:
        stream = sys.stdout
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        super().__init__(stream=stream)
