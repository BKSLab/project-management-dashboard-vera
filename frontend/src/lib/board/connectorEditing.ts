import { clampCoordinate } from "@/lib/board/geometry";
import { preservePolyline } from "@/lib/board/routing";
import { withConnectorGeometry, type LocalRef, type ShapeObject } from "@/lib/board/scene";
import type { Point } from "@/lib/board/types";

export type ConnectorAction = "reverse" | "reset-route" | "detach-start" | "detach-end";

export function changeConnectorEndpoint(object: ShapeObject, end: "start" | "end", point: Point, ref: LocalRef | null): ShapeObject {
    const stored = object.points ?? [point, point];
    const start = end === "start" ? point : stored[0];
    const finish = end === "end" ? point : stored[stored.length - 1];
    const points = stored.length > 2 ? preservePolyline(stored, start, finish, object.style.route) : [start, finish];
    return withConnectorGeometry({
        ...object,
        startRef: end === "start" ? ref : object.startRef,
        endRef: end === "end" ? ref : object.endRef,
    }, points);
}

export function editConnectorBend(object: ShapeObject, index: number, point: Point, insert: boolean): ShapeObject {
    const stored = object.points ?? [];
    const last = stored.length - 1;
    if ((insert && (index < 0 || index >= last)) || (!insert && (index <= 0 || index >= last))) {
        throw new Error("Выберите внутреннюю точку или сегмент связи.");
    }
    const target: Point = [clampCoordinate(point[0]), clampCoordinate(point[1])];
    let points: Point[] = stored.map(item => [...item]);
    if (insert) {
        const a = stored[index], b = stored[index + 1];
        let added: Point[];
        if (object.style.route === "orthogonal" && a[1] === b[1]) {
            if (target[1] === a[1]) return object;
            added = [[a[0], target[1]], [b[0], target[1]]];
        } else if (object.style.route === "orthogonal" && a[0] === b[0]) {
            if (target[0] === a[0]) return object;
            added = [[target[0], a[1]], [target[0], b[1]]];
        } else {
            added = [target];
        }
        points = [...points.slice(0, index + 1), ...added, ...points.slice(index + 1)];
    } else {
        if (object.style.route === "orthogonal") {
            // Propagate the coordinate along the entire collinear chain, not
            // only the immediate neighbor. A chain reaching an endpoint is fixed.
            for (const axis of [0, 1] as const) {
                let first = index, final = index;
                while (first > 0 && stored[first - 1][axis] === stored[first][axis]) first -= 1;
                while (final < last && stored[final + 1][axis] === stored[final][axis]) final += 1;
                if (first === 0) target[axis] = stored[0][axis];
                else if (final === last) target[axis] = stored[last][axis];
                for (let member = first; member <= final; member += 1) points[member][axis] = target[axis];
            }
        } else {
            points[index] = target;
        }
    }
    if (points.length > 50) throw new Error("В одной связи может быть не более 50 точек.");
    return withConnectorGeometry(object, points);
}
