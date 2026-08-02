"""Генерирует базовый JSON-снэпшот ИСР из эталонного docs/AGENT_VERA_WBS.txt.

Не трогает БД — парсит канонический текстовый файл (тот же формат, что разбирает
seed_initial_data.py) и сохраняет результат в backend/scripts/data/wbs_seed.json.
Этот JSON — «базовая версия» ИСР, с которой стартует чистая БД при деплое
(см. seed_from_json.py), независимо от того, что накопилось в текущей dev-БД.

Запуск (из каталога backend, БД не требуется):
    PYTHONPATH=. venv/Scripts/python.exe scripts/export_wbs_json.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WBS_TXT_PATH = PROJECT_ROOT / "docs" / "AGENT_VERA_WBS.txt"
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "wbs_seed.json"

PHASE_RE = re.compile(r"^ФАЗА\s+\d+\.\s+(.+)$")
CROSS_CUTTING_RE = re.compile(r"^СКВОЗНЫЕ ЗАДАЧИ")
ITEM2_RE = re.compile(r"^(\d+\.\d+)\s+(.+?)(?:\s*\[([\w-]+)\])?\s*$")
ITEM3_RE = re.compile(r"^(\d+\.\d+\.\d+)\s+(.+?)\s*$")

ROLE_ALIASES = {
    "UX-R": "UXR",
    "UX-D": "UXD",
    "Backend": "BE",
    "Frontend": "FE",
    "Expert": "EXPERT",
}
KNOWN_ROLES = {"PM", "BE", "FE", "UXR", "UXD", "EXPERT", "QA", "BA", "MKT"}


def resolve_role(raw_role: str | None) -> str | None:
    if raw_role is None:
        return None
    canonical = ROLE_ALIASES.get(raw_role, raw_role)
    if canonical not in KNOWN_ROLES:
        print(f"⚠️ Неизвестная роль ИСР: {raw_role!r}, сохранена как null", file=sys.stderr)
        return None
    return canonical


def parse_wbs(text: str) -> list[dict]:
    """Парсит AGENT_VERA_WBS.txt в плоский список узлов с указанием родителя по коду."""
    nodes: list[dict] = []
    phase_index = 0
    current_phase_code: str | None = None
    current_item2_code: str | None = None
    phase_order = 0
    item2_order = 0
    item3_order = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        phase_match = PHASE_RE.match(line)
        cross_match = CROSS_CUTTING_RE.match(line)
        if phase_match or cross_match:
            phase_index += 1
            current_phase_code = str(phase_index)
            current_item2_code = None
            item2_order = 0
            phase_name = phase_match.group(1) if phase_match else line
            nodes.append(
                {
                    "code": current_phase_code,
                    "parent_code": None,
                    "phase_name": phase_name,
                    "title": phase_name,
                    "role": None,
                    "order_index": phase_order,
                    "is_leaf": False,
                }
            )
            phase_order += 1
            continue

        if raw_line.startswith("    ") and not raw_line.startswith("     "):
            item3_match = ITEM3_RE.match(line)
            if item3_match and current_item2_code:
                code, title = item3_match.groups()
                nodes.append(
                    {
                        "code": code,
                        "parent_code": current_item2_code,
                        "phase_name": None,
                        "title": title,
                        "role": None,
                        "order_index": item3_order,
                        "is_leaf": True,
                    }
                )
                item3_order += 1
            continue

        item2_match = ITEM2_RE.match(line)
        if item2_match and current_phase_code:
            code, title, role = item2_match.groups()
            if not re.match(r"^\d+\.\d+$", code):
                continue
            current_item2_code = code
            item3_order = 0
            nodes.append(
                {
                    "code": code,
                    "parent_code": current_phase_code,
                    "phase_name": None,
                    "title": title.strip(),
                    "role": resolve_role(role),
                    "order_index": item2_order,
                    "is_leaf": False,
                }
            )
            item2_order += 1

    return nodes


def main() -> None:
    if not WBS_TXT_PATH.exists():
        raise SystemExit(f"Файл ИСР не найден: {WBS_TXT_PATH}")

    text = WBS_TXT_PATH.read_text(encoding="utf-8")
    nodes = parse_wbs(text)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done: exported {len(nodes)} WBS nodes from {WBS_TXT_PATH.name} to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
