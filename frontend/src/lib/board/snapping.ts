import type { Box } from "@/lib/board/geometry";
import type { Point } from "@/lib/board/types";

export const GRID_SIZE = 8;
/** Порог прилипания к соседям — в экранных пикселях, делится на масштаб. */
export const SNAP_SCREEN_PX = 6;

/** Направляющая: вертикальная линия x=pos (axis "x") или горизонтальная y=pos. */
export interface Guide {
    axis: "x" | "y";
    pos: number;
    from: number;
    to: number;
}

export function snapValue(value: number, grid = GRID_SIZE): number {
    return Math.round(value / grid) * grid;
}

export function snapPoint(point: Point, grid = GRID_SIZE): Point {
    return [snapValue(point[0], grid), snapValue(point[1], grid)];
}

function axisLines(box: Box, axis: "x" | "y"): number[] {
    return axis === "x" ? [box.x, box.x + box.w / 2, box.x + box.w] : [box.y, box.y + box.h / 2, box.y + box.h];
}

interface AxisMatch {
    delta: number;
    pos: number;
    other: Box;
}

/** Ближайшее совпадение одной из линий (края/центр) с линиями соседей. */
function bestMatch(values: number[], others: Box[], axis: "x" | "y", threshold: number): AxisMatch | null {
    let best: AxisMatch | null = null;
    for (const other of others) {
        for (const target of axisLines(other, axis)) {
            for (const value of values) {
                const delta = target - value;
                if (Math.abs(delta) <= threshold && (!best || Math.abs(delta) < Math.abs(best.delta))) {
                    best = { delta, pos: target, other };
                }
            }
        }
    }
    return best;
}

function guideFor(axis: "x" | "y", pos: number, a: Box, b: Box): Guide {
    if (axis === "x") {
        return { axis, pos, from: Math.min(a.y, b.y), to: Math.max(a.y + a.h, b.y + b.h) };
    }
    return { axis, pos, from: Math.min(a.x, b.x), to: Math.max(a.x + a.w, b.x + b.w) };
}

/**
 * Прилипание перемещаемой рамки: сначала к краям и центрам соседей (с направляющей),
 * иначе левый-верхний угол — к сетке 8px.
 */
export function snapMove(moving: Box, others: Box[], threshold: number, grid = GRID_SIZE): { box: Box; guides: Guide[] } {
    const guides: Guide[] = [];
    let { x, y } = moving;
    const matchX = bestMatch(axisLines(moving, "x"), others, "x", threshold);
    if (matchX) x += matchX.delta;
    else x = snapValue(x, grid);
    const matchY = bestMatch(axisLines(moving, "y"), others, "y", threshold);
    if (matchY) y += matchY.delta;
    else y = snapValue(y, grid);
    const box = { ...moving, x, y };
    if (matchX) guides.push(guideFor("x", matchX.pos, box, matchX.other));
    if (matchY) guides.push(guideFor("y", matchY.pos, box, matchY.other));
    return { box, guides };
}

export type ResizeHandle = "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw";

export const RESIZE_HANDLES: ResizeHandle[] = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];

export interface ResizeLimits {
    minW: number;
    minH: number;
    maxW: number;
    maxH: number;
}

/**
 * Новая рамка при протяжке ручки на (dx, dy). keepRatio (Shift) — пропорции исходной.
 * Размер зажат в лимиты, противоположный край стоит на месте.
 */
export function resizeBox(origin: Box, handle: ResizeHandle, dx: number, dy: number, limits: ResizeLimits, keepRatio = false): Box {
    const west = handle.includes("w");
    const east = handle.includes("e");
    const north = handle.includes("n");
    const south = handle.includes("s");
    let w = origin.w + (east ? dx : west ? -dx : 0);
    let h = origin.h + (south ? dy : north ? -dy : 0);
    if (keepRatio && origin.w > 0 && origin.h > 0) {
        const ratio = origin.w / origin.h;
        if ((east || west) && (north || south)) {
            if (Math.abs(w / origin.w) >= Math.abs(h / origin.h)) h = w / ratio;
            else w = h * ratio;
        } else if (east || west) {
            h = w / ratio;
        } else {
            w = h * ratio;
        }
    }
    w = Math.max(limits.minW, Math.min(limits.maxW, w));
    h = Math.max(limits.minH, Math.min(limits.maxH, h));
    const x = west ? origin.x + origin.w - w : east ? origin.x : origin.x + (origin.w - w) / 2;
    const y = north ? origin.y + origin.h - h : south ? origin.y : origin.y + (origin.h - h) / 2;
    return { x, y, w, h };
}

/** Прилипание края, который тянут, к соседям или сетке (противоположный край неподвижен). */
export function snapResize(box: Box, handle: ResizeHandle, others: Box[], threshold: number, limits: ResizeLimits, grid = GRID_SIZE): { box: Box; guides: Guide[] } {
    const guides: Guide[] = [];
    let { x, y, w, h } = box;
    const snapEdge = (value: number, axis: "x" | "y"): { value: number; match: AxisMatch | null } => {
        const match = bestMatch([value], others, axis, threshold);
        return { value: match ? value + match.delta : snapValue(value, grid), match };
    };
    if (handle.includes("e")) {
        const { value, match } = snapEdge(x + w, "x");
        const next = Math.max(limits.minW, Math.min(limits.maxW, value - x));
        w = next;
        if (match) guides.push(guideFor("x", match.pos, { x, y, w, h }, match.other));
    } else if (handle.includes("w")) {
        const right = x + w;
        const { value, match } = snapEdge(x, "x");
        w = Math.max(limits.minW, Math.min(limits.maxW, right - value));
        x = right - w;
        if (match) guides.push(guideFor("x", match.pos, { x, y, w, h }, match.other));
    }
    if (handle.includes("s")) {
        const { value, match } = snapEdge(y + h, "y");
        h = Math.max(limits.minH, Math.min(limits.maxH, value - y));
        if (match) guides.push(guideFor("y", match.pos, { x, y, w, h }, match.other));
    } else if (handle.includes("n")) {
        const bottom = y + h;
        const { value, match } = snapEdge(y, "y");
        h = Math.max(limits.minH, Math.min(limits.maxH, bottom - value));
        y = bottom - h;
        if (match) guides.push(guideFor("y", match.pos, { x, y, w, h }, match.other));
    }
    return { box: { x, y, w, h }, guides };
}
