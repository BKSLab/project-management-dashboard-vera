import type { Point, ShapeKind } from "@/lib/board/types";

/** Прямоугольник в координатах холста. */
export interface Box {
    x: number;
    y: number;
    w: number;
    h: number;
}

export const MIN_SHAPE_SIZE = 8;
export const MAX_SHAPE_SIZE = 20_000;
export const MAX_COORDINATE = 1_000_000;

export function clampCoordinate(value: number): number {
    const finite = Number.isFinite(value) ? value : 0;
    return Math.max(-MAX_COORDINATE, Math.min(MAX_COORDINATE, Math.round(finite * 10) / 10));
}

export function boxRight(box: Box): number {
    return box.x + box.w;
}

export function boxBottom(box: Box): number {
    return box.y + box.h;
}

export function boxCenter(box: Box): Point {
    return [box.x + box.w / 2, box.y + box.h / 2];
}

export function unionBoxes(boxes: Box[]): Box | null {
    if (boxes.length === 0) return null;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const box of boxes) {
        minX = Math.min(minX, box.x);
        minY = Math.min(minY, box.y);
        maxX = Math.max(maxX, box.x + box.w);
        maxY = Math.max(maxY, box.y + box.h);
    }
    return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

export function boxesIntersect(a: Box, b: Box): boolean {
    return a.x <= b.x + b.w && a.x + a.w >= b.x && a.y <= b.y + b.h && a.y + a.h >= b.y;
}

export function boxContainsPoint(box: Box, point: Point, margin = 0): boolean {
    return point[0] >= box.x - margin
        && point[0] <= box.x + box.w + margin
        && point[1] >= box.y - margin
        && point[1] <= box.y + box.h + margin;
}

export function inflateBox(box: Box, by: number): Box {
    return { x: box.x - by, y: box.y - by, w: box.w + by * 2, h: box.h + by * 2 };
}

export function boundsOfPoints(points: Point[]): Box {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const [x, y] of points) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
    }
    if (!Number.isFinite(minX)) return { x: 0, y: 0, w: 0, h: 0 };
    return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

/**
 * Прямоугольник по двум точкам протяжки мышью. Shift — квадрат (круг),
 * сторона — по большей проекции, угол растёт в сторону курсора.
 */
export function boxFromDrag(start: Point, current: Point, square = false): Box {
    let dx = current[0] - start[0];
    let dy = current[1] - start[1];
    if (square) {
        const side = Math.max(Math.abs(dx), Math.abs(dy));
        dx = Math.sign(dx || 1) * side;
        dy = Math.sign(dy || 1) * side;
    }
    return {
        x: Math.min(start[0], start[0] + dx),
        y: Math.min(start[1], start[1] + dy),
        w: Math.abs(dx),
        h: Math.abs(dy),
    };
}

/** Угол, кратный 45°, от точки start — для линий и стрелок с Shift. */
export function constrainAngle(start: Point, current: Point): Point {
    const dx = current[0] - start[0];
    const dy = current[1] - start[1];
    const length = Math.hypot(dx, dy);
    if (length === 0) return current;
    const step = Math.PI / 4;
    const angle = Math.round(Math.atan2(dy, dx) / step) * step;
    return [start[0] + Math.round(Math.cos(angle) * length * 100) / 100, start[1] + Math.round(Math.sin(angle) * length * 100) / 100];
}

/** Контур фигуры в локальных координатах svg размером w×h (с отступом на толщину). */
export function shapePath(kind: ShapeKind, w: number, h: number, inset = 0): string {
    const x0 = inset;
    const y0 = inset;
    const x1 = Math.max(inset, w - inset);
    const y1 = Math.max(inset, h - inset);
    const cx = w / 2;
    const cy = h / 2;
    if (kind === "ellipse") {
        const rx = Math.max(0, (x1 - x0) / 2);
        const ry = Math.max(0, (y1 - y0) / 2);
        return `M ${cx - rx} ${cy} A ${rx} ${ry} 0 1 0 ${cx + rx} ${cy} A ${rx} ${ry} 0 1 0 ${cx - rx} ${cy} Z`;
    }
    if (kind === "diamond") {
        return `M ${cx} ${y0} L ${x1} ${cy} L ${cx} ${y1} L ${x0} ${cy} Z`;
    }
    const r = Math.min(6, (x1 - x0) / 4, (y1 - y0) / 4);
    if (r <= 0.5) return `M ${x0} ${y0} H ${x1} V ${y1} H ${x0} Z`;
    return `M ${x0 + r} ${y0} H ${x1 - r} Q ${x1} ${y0} ${x1} ${y0 + r} V ${y1 - r} Q ${x1} ${y1} ${x1 - r} ${y1} H ${x0 + r} Q ${x0} ${y1} ${x0} ${y1 - r} V ${y0 + r} Q ${x0} ${y0} ${x0 + r} ${y0} Z`;
}

export function polylinePath(points: Point[], offsetX = 0, offsetY = 0): string {
    return points
        .map(([x, y], index) => `${index === 0 ? "M" : "L"} ${round2(x - offsetX)} ${round2(y - offsetY)}`)
        .join(" ");
}

/** Точка на середине длины ломаной — там стоит подпись стрелки. */
export function polylineMidpoint(points: Point[]): Point {
    if (points.length === 0) return [0, 0];
    if (points.length === 1) return points[0];
    const lengths: number[] = [];
    let total = 0;
    for (let index = 1; index < points.length; index += 1) {
        const length = Math.hypot(points[index][0] - points[index - 1][0], points[index][1] - points[index - 1][1]);
        lengths.push(length);
        total += length;
    }
    let remaining = total / 2;
    for (let index = 1; index < points.length; index += 1) {
        const length = lengths[index - 1];
        if (remaining <= length && length > 0) {
            const t = remaining / length;
            return [
                points[index - 1][0] + (points[index][0] - points[index - 1][0]) * t,
                points[index - 1][1] + (points[index][1] - points[index - 1][1]) * t,
            ];
        }
        remaining -= length;
    }
    return points[points.length - 1];
}

/** Расстояние от точки до ломаной — попадание по тонкой стрелке. */
export function distanceToPolyline(point: Point, points: Point[]): number {
    let best = Infinity;
    for (let index = 1; index < points.length; index += 1) {
        best = Math.min(best, distanceToSegment(point, points[index - 1], points[index]));
    }
    return best;
}

export function distanceToSegment(point: Point, a: Point, b: Point): number {
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const lengthSq = dx * dx + dy * dy;
    if (lengthSq === 0) return Math.hypot(point[0] - a[0], point[1] - a[1]);
    const t = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / lengthSq));
    return Math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy));
}

export function round2(value: number): number {
    return Math.round(value * 100) / 100;
}

/** Попадает ли объект в видимую область холста (с запасом) — невидимые не рендерим. */
export function isBoxVisible(box: Box, viewport: Box, margin = 0): boolean {
    return boxesIntersect(box, inflateBox(viewport, margin));
}
