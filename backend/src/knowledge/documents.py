from __future__ import annotations

from dataclasses import dataclass

from src.db.models.wbs_nodes import WbsNode


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Текст и payload одного детерминированного Qdrant point."""

    point_id: str
    text: str
    payload: dict


def build_wbs_paths(nodes: list[WbsNode]) -> dict[int, str]:
    """Вычисляет человекочитаемый путь каждого узла ИСР."""
    by_id = {node.id: node for node in nodes}
    paths: dict[int, str] = {}
    for node in nodes:
        titles: list[str] = []
        current: WbsNode | None = node
        visited: set[int] = set()
        while current is not None and current.id not in visited:
            visited.add(current.id)
            titles.append(current.title)
            current = by_id.get(current.parent_id) if current.parent_id is not None else None
        paths[node.id] = " / ".join(reversed(titles))
    return paths
