import { MAX_COORDINATE, unionBoxes, type Box } from "@/lib/board/geometry";
import { assertRigidGroupMovement, expandGroupSelection, lockedSelection, type BoardGrouping } from "@/lib/board/group";
import { isConnector, syncConnectors, type Scene, type SceneObject } from "@/lib/board/scene";

export type Alignment = "left" | "center" | "right" | "top" | "middle" | "bottom";
export type DistributionAxis = "horizontal" | "vertical";

interface LayoutUnit { keys: string[]; box: Box }
const EMPTY_GROUPING: BoardGrouping = { groups: [], locked: [] };

function units(scene: Scene, keys: Iterable<string>, state: BoardGrouping): LayoutUnit[] {
    const selected = expandGroupSelection(keys, state.groups);
    const blocked = new Set(state.locked);
    const seen = new Set<string>();
    const result: LayoutUnit[] = [];
    for (const key of selected) {
        if (seen.has(key) || !scene.has(key)) continue;
        const group = state.groups.find((item) => item.members.includes(key));
        const members = (group?.members ?? [key]).filter((member) => scene.has(member));
        members.forEach((member) => seen.add(member));
        // Connectors with live anchors follow nodes, rather than moving independently.
        const objects = members.map((member) => scene.get(member)!);
        if (members.some((member) => blocked.has(member))) continue;
        if (!group && objects.some((object) => object.type === "shape" && isConnector(object)
            && (object.startRef || object.endRef))) continue;
        if (objects.some((object) => ![object.x, object.y, object.w, object.h].every(Number.isFinite))) {
            throw new Error("Не удалось прочитать координаты объектов.");
        }
        const box = unionBoxes(objects)!;
        result.push({ keys: members, box });
    }
    return result;
}

function move(unit: LayoutUnit, dx: number, dy: number, scene: Scene, updates: Map<string, SceneObject>): void {
    if ((dx !== 0 || dy !== 0) && unit.keys.length > 1) assertRigidGroupMovement(scene, unit.keys);
    for (const key of unit.keys) {
        const object = scene.get(key)!;
        if (Math.abs(object.x + dx) > MAX_COORDINATE || Math.abs(object.y + dy) > MAX_COORDINATE
            || (object.type === "shape" && object.points?.some(([x, y]) =>
                Math.abs(x + dx) > MAX_COORDINATE || Math.abs(y + dy) > MAX_COORDINATE))) {
            throw new Error("Выравнивание выходит за границы доски.");
        }
        if (dx === 0 && dy === 0) continue;
        const next: SceneObject = object.type === "shape"
            ? { ...object, x: object.x + dx, y: object.y + dy,
                points: object.points?.map(([x, y]) => [x + dx, y + dy]) ?? null }
            : { ...object, x: object.x + dx, y: object.y + dy };
        updates.set(key, next);
    }
}

function withConnections(scene: Scene, updates: Map<string, SceneObject>, state: BoardGrouping): Map<string, SceneObject> {
    const next = new Map(scene);
    updates.forEach((object, key) => next.set(key, object));
    // Include attached connectors in the same history/save operation.
    syncConnectors(next, new Set(updates.keys())).forEach((object, key) => {
        if (lockedSelection([key], state)) throw new Error("Выравнивание изменяет заблокированную связь. Сначала разблокируйте её.");
        updates.set(key, object);
    });
    for (const object of updates.values()) {
        if (![object.x, object.y].every((value) => Number.isFinite(value) && Math.abs(value) <= MAX_COORDINATE)
            || (object.type === "shape" && object.points?.some((point) =>
                !point.every((value) => Number.isFinite(value) && Math.abs(value) <= MAX_COORDINATE)))) {
            throw new Error("Выравнивание выходит за границы доски.");
        }
    }
    return updates;
}

export function alignObjects(
    scene: Scene, keys: Iterable<string>, alignment: Alignment, state: BoardGrouping = EMPTY_GROUPING,
): Map<string, SceneObject> {
    const selected = units(scene, keys, state);
    const updates = new Map<string, SceneObject>();
    if (selected.length < 2) return updates;
    const box = unionBoxes(selected.map((unit) => unit.box))!;
    for (const unit of selected) {
        let dx = 0, dy = 0;
        switch (alignment) {
            case "left": dx = box.x - unit.box.x; break;
            case "center": dx = box.x + box.w / 2 - unit.box.x - unit.box.w / 2; break;
            case "right": dx = box.x + box.w - unit.box.x - unit.box.w; break;
            case "top": dy = box.y - unit.box.y; break;
            case "middle": dy = box.y + box.h / 2 - unit.box.y - unit.box.h / 2; break;
            case "bottom": dy = box.y + box.h - unit.box.y - unit.box.h; break;
        }
        move(unit, dx, dy, scene, updates);
    }
    return withConnections(scene, updates, state);
}

/** Equal edge-to-edge gaps; first and last units retain their positions. */
export function distributeObjects(
    scene: Scene, keys: Iterable<string>, axis: DistributionAxis, state: BoardGrouping = EMPTY_GROUPING,
): Map<string, SceneObject> {
    const selected = units(scene, keys, state);
    const updates = new Map<string, SceneObject>();
    if (selected.length < 3) return updates;
    const horizontal = axis === "horizontal";
    const pos = (unit: LayoutUnit) => horizontal ? unit.box.x : unit.box.y;
    const size = (unit: LayoutUnit) => horizontal ? unit.box.w : unit.box.h;
    selected.sort((a, b) => pos(a) - pos(b) || a.keys[0].localeCompare(b.keys[0]));
    const first = selected[0], last = selected[selected.length - 1];
    const span = pos(last) + size(last) - pos(first);
    const gap = (span - selected.reduce((sum, unit) => sum + size(unit), 0)) / (selected.length - 1);
    let cursor = pos(first) + size(first) + gap;
    for (let index = 1; index < selected.length - 1; index += 1) {
        const unit = selected[index], delta = cursor - pos(unit);
        move(unit, horizontal ? delta : 0, horizontal ? 0 : delta, scene, updates);
        cursor += size(unit) + gap;
    }
    return withConnections(scene, updates, state);
}
