"""Выгрузка машиночитаемого списка инструментов MCP в ``docs/mcp-tools.json``
и его копию ``frontend/src/lib/help/mcp-tools.json``.

Копию читает фронт для справки «API и MCP» (контекст Docker-сборки фронта —
только ``frontend/``, поэтому файл лежит в двух местах); собирается из реестра
``registry.tt_tool`` и входных схем сервера, поэтому не расходится с тем,
что видит агент. Расхождение ловит тест ``test_mcp_tools_json``.

Запуск из каталога ``backend``: ``python -m src.mcp_server.export_tools``.
"""

import json
import sys
from pathlib import Path

from src.mcp_server.registry import tool_catalog
from src.mcp_server.server import mcp_server  # noqa: F401  регистрирует инструменты

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_JSON = REPO_ROOT / "docs" / "mcp-tools.json"
FRONTEND_TOOLS_JSON = REPO_ROOT / "frontend" / "src" / "lib" / "help" / "mcp-tools.json"
TOOLS_JSON_TARGETS = (TOOLS_JSON, FRONTEND_TOOLS_JSON)


def render() -> str:
    """Возвращает содержимое файла со стабильным порядком и переводом строки в конце."""
    return json.dumps(tool_catalog(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    """Перезаписывает оба файла одним содержимым."""
    content = render()
    for target in TOOLS_JSON_TARGETS:
        target.write_text(content, encoding="utf-8")
        print(f"✅ {target} обновлён.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
