import { anchorDirection } from "@/lib/board/anchors";
import type { Anchor, Point } from "@/lib/board/types";

export type Route = "straight" | "orthogonal";

function sameAxis(a: Point, b: Point): boolean {
    return (a[0] !== 0 && b[0] !== 0) || (a[1] !== 0 && b[1] !== 0);
}

/**
 * Маршрут стрелки между двумя точками.
 * straight — отрезок. orthogonal — ломаная под прямым углом по простому правилу:
 * обе стороны выхода по одной оси → 3 сегмента через середину, по разным → 2 сегмента (угол).
 * Сторона выхода берётся из точки привязки, без неё — по преобладающей оси.
 */
export function routeConnector(
    start: Point,
    end: Point,
    route: Route,
    startAnchor?: Anchor | null,
    endAnchor?: Anchor | null,
): Point[] {
    if (route === "straight") return [start, end];
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    if (dx === 0 || dy === 0) return [start, end];
    const horizontalFirst = Math.abs(dx) >= Math.abs(dy);
    const startDir = anchorDirection(startAnchor) ?? (horizontalFirst ? [Math.sign(dx), 0] : [0, Math.sign(dy)]);
    const endDir = anchorDirection(endAnchor) ?? (horizontalFirst ? [-Math.sign(dx), 0] : [0, -Math.sign(dy)]);
    let points: Point[];
    if (sameAxis(startDir, endDir)) {
        if (startDir[0] !== 0) {
            const midX = (start[0] + end[0]) / 2;
            points = [start, [midX, start[1]], [midX, end[1]], end];
        } else {
            const midY = (start[1] + end[1]) / 2;
            points = [start, [start[0], midY], [end[0], midY], end];
        }
    } else if (startDir[0] !== 0) {
        points = [start, [end[0], start[1]], end];
    } else {
        points = [start, [start[0], end[1]], end];
    }
    return simplifyPolyline(points);
}

/** Убирает повторы и точки на одной прямой — меньше данных, ровнее подпись. */
export function simplifyPolyline(points: Point[]): Point[] {
    const result: Point[] = [];
    for (const point of points) {
        const last = result[result.length - 1];
        if (last && last[0] === point[0] && last[1] === point[1]) continue;
        if (result.length >= 2) {
            const prev = result[result.length - 2];
            const collinear = (last[0] === prev[0] && last[0] === point[0]) || (last[1] === prev[1] && last[1] === point[1]);
            if (collinear) {
                result[result.length - 1] = point;
                continue;
            }
        }
        result.push(point);
    }
    return result.length >= 2 ? result : [points[0], points[points.length - 1]];
}

/** Keep custom bends while the referenced endpoints move. */
export function preservePolyline(points: Point[], start: Point, end: Point, route: Route): Point[] {
    const last = points.length - 1;
    const dx = start[0] - points[0][0], dy = start[1] - points[0][1];
    if (Math.abs(dx - (end[0] - points[last][0])) < 0.001 && Math.abs(dy - (end[1] - points[last][1])) < 0.001) {
        return points.map(point => [point[0] + dx, point[1] + dy]);
    }
    const next: Point[] = points.map(point => [...point]);
    next[0] = [...start]; next[last] = [...end];
    if (route === "orthogonal" && points.length > 2) {
        // A fully collinear path has no custom bends to preserve. When its ends
        // diverge, add a valid elbow rather than creating a diagonal segment.
        if (points.every(point => point[0] === points[0][0]) || points.every(point => point[1] === points[0][1])) {
            return routeConnector(start, end, route);
        }
        let first = 1, final = last - 1;
        while (first < last && points[first][0] === points[0][0] && points[first][1] === points[0][1]) first += 1;
        while (final > 0 && points[final][0] === points[last][0] && points[final][1] === points[last][1]) final -= 1;
        if (points[first][1] === points[0][1]) {
            for (let i = 1; i < last && points[i][1] === points[0][1]; i += 1) next[i][1] = start[1];
        } else if (points[first][0] === points[0][0]) {
            for (let i = 1; i < last && points[i][0] === points[0][0]; i += 1) next[i][0] = start[0];
        }
        if (points[final][1] === points[last][1]) {
            for (let i = last - 1; i > 0 && points[i][1] === points[last][1]; i -= 1) next[i][1] = end[1];
        } else if (points[final][0] === points[last][0]) {
            for (let i = last - 1; i > 0 && points[i][0] === points[last][0]; i -= 1) next[i][0] = end[0];
        }
    }
    return next;
}

/**
 * Треугольник наконечника на конце tip, направленный от from к tip.
 * Размер растёт с толщиной линии.
 */
export function arrowHeadPolygon(from: Point, tip: Point, strokeWidth: number): Point[] {
    const size = 7 + strokeWidth * 2;
    const angle = Math.atan2(tip[1] - from[1], tip[0] - from[0]);
    const spread = Math.PI / 7;
    return [
        tip,
        [tip[0] - size * Math.cos(angle - spread), tip[1] - size * Math.sin(angle - spread)],
        [tip[0] - size * Math.cos(angle + spread), tip[1] - size * Math.sin(angle + spread)],
    ];
}
