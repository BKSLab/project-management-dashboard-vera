"""Защита явных блокировок, включая стрелки, затронутые перемещением узла."""

from collections.abc import Iterable
from typing import Any

from src.db.models.board_shapes import BoardShape


def locked_object_refs(metadata: dict[str, Any]) -> set[tuple[str, int]]:
    locked = {(ref["type"], ref["id"]) for ref in metadata.get("locked", [])}
    for group in metadata.get("groups", []):
        members = {(ref["type"], ref["id"]) for ref in group["members"]}
        if members & locked:
            locked.update(members)
    return locked


def mutation_is_locked(
    metadata: dict[str, Any],
    changed: Iterable[tuple[str, int]],
    shapes: Iterable[BoardShape],
    indirect: Iterable[tuple[str, int]] | None = None,
) -> bool:
    keys = set(changed)
    indirect_keys = keys if indirect is None else set(indirect)
    locked = locked_object_refs(metadata)
    if keys & locked:
        return True
    for shape in shapes:
        if ("shape", shape.id) not in locked:
            continue
        refs = [ref for ref in (shape.start_ref, shape.end_ref) if ref is not None]
        if any((ref["type"], ref["id"]) in indirect_keys for ref in refs):
            return True
    return False


def rewrite_metadata_refs(
    metadata: dict, removed: set[tuple[str, int]], replacement: dict | None = None
) -> dict:
    """Сохраняет группы при замене объекта и убирает ссылки на удалённые."""

    def update(ref):
        key = (ref["type"], ref["id"])
        if replacement and key in replacement:
            return replacement[key]
        return None if key in removed else ref

    groups = [
        {
            **group,
            "members": [value for ref in group["members"] if (value := update(ref)) is not None],
        }
        for group in metadata.get("groups", [])
    ]
    return {
        **metadata,
        "groups": [group for group in groups if len(group["members"]) >= 2],
        "locked": [
            value for ref in metadata.get("locked", []) if (value := update(ref)) is not None
        ],
    }
