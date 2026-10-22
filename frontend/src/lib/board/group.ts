import type { Scene } from "@/lib/board/scene";

/** A group cannot move rigidly while one of its connectors is anchored outside it. */
export function assertRigidGroupMovement(scene: Scene, members: Iterable<string>): void {
    const keys = new Set(members);
    for (const key of keys) {
        const object = scene.get(key);
        if (object?.type !== "shape" || (object.kind !== "arrow" && object.kind !== "line")) continue;
        if ([object.startRef, object.endRef].some((ref) => ref && scene.has(ref.key) && !keys.has(ref.key))) {
            throw new Error("Группа связана с внешним объектом. Включите его в группу или отсоедините связь.");
        }
    }
}

export interface BoardGroup {
    id: string;
    name: string;
    members: string[];
}

/** Local keys are converted to server IDs by metadata.ts before saving. */
export interface BoardGrouping {
    groups: BoardGroup[];
    locked: string[];
}

export function expandGroupSelection(keys: Iterable<string>, groups: readonly BoardGroup[]): Set<string> {
    const selected = new Set(keys);
    for (const group of groups) {
        if (group.members.some((key) => selected.has(key))) {
            group.members.forEach((key) => selected.add(key));
        }
    }
    return selected;
}

export function lockedSelection(keys: Iterable<string>, state: BoardGrouping): boolean {
    const selected = expandGroupSelection(keys, state.groups);
    return state.locked.some((key) => selected.has(key));
}

/** Disjoint, explicit groups: regrouping merges selected groups. */
export function groupSelection(
    scene: Scene, state: BoardGrouping, keys: Iterable<string>, name: string, id: string,
): BoardGrouping {
    if (!name.trim() || !id.trim()) throw new Error("Укажите название группы.");
    const members = [...expandGroupSelection(keys, state.groups)].filter((key) => scene.has(key));
    if (members.length < 2) throw new Error("Выделите хотя бы два объекта.");
    if (lockedSelection(members, state)) throw new Error("Сначала разблокируйте объекты.");
    const selected = new Set(members);
    const groups = state.groups.filter((group) => !group.members.some((key) => selected.has(key)));
    if (groups.some((group) => group.id === id)) throw new Error("Группа с таким идентификатором уже есть.");
    return { ...state, groups: [...groups, { id, name: name.trim(), members }] };
}

export function ungroupSelection(state: BoardGrouping, keys: Iterable<string>): BoardGrouping {
    const selected = new Set(keys);
    if (lockedSelection(selected, state)) throw new Error("Сначала разблокируйте группу.");
    return { ...state, groups: state.groups.filter((group) => !group.members.some((key) => selected.has(key))) };
}

/** Lock/unlock an entire group, even if only one member was hit. */
export function setSelectionLocked(state: BoardGrouping, keys: Iterable<string>, locked: boolean): BoardGrouping {
    const selected = expandGroupSelection(keys, state.groups);
    const next = new Set(state.locked);
    selected.forEach((key) => { if (locked) next.add(key); else next.delete(key); });
    return { ...state, locked: [...next] };
}

/** Used after delete/undo/server reload; never infer grouping from containment. */
export function pruneGrouping(state: BoardGrouping, scene: Scene): BoardGrouping {
    return {
        groups: state.groups
            .map((group) => ({ ...group, members: group.members.filter((key) => scene.has(key)) }))
            .filter((group) => group.members.length > 1),
        locked: state.locked.filter((key) => scene.has(key)),
    };
}

/** All mutation entry points (keyboard, properties, drag, delete) use the same guard. */
export function editableSelection(scene: Scene, state: BoardGrouping, keys: Iterable<string>): Set<string> {
    const selected = expandGroupSelection(keys, state.groups);
    if (lockedSelection(selected, state)) return new Set();
    return new Set([...selected].filter((key) => scene.has(key)));
}
