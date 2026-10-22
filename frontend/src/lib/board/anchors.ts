import { boxCenter, boxContainsPoint, type Box } from "@/lib/board/geometry";
import type { Anchor, Point, ShapeKind } from "@/lib/board/types";

/** Узел, к которому цепляется стрелка: фигура или стикер. */
export interface AnchorNode {
    key: string;
    kind: ShapeKind | "sticker";
    box: Box;
    z: number;
}

export const ANCHORS: Anchor[] = ["top", "right", "bottom", "left", "center"];

export function anchorPoint(box: Box, anchor: Anchor): Point {
    switch (anchor) {
        case "top":
            return [box.x + box.w / 2, box.y];
        case "right":
            return [box.x + box.w, box.y + box.h / 2];
        case "bottom":
            return [box.x + box.w / 2, box.y + box.h];
        case "left":
            return [box.x, box.y + box.h / 2];
        default:
            return boxCenter(box);
    }
}

/**
 * Куда «смотрит» точка привязки: стрелка выходит из узла в эту сторону.
 * У центра стороны нет — её выбирает маршрутизатор по взаимному положению.
 */
export function anchorDirection(anchor: Anchor | null | undefined): Point | null {
    switch (anchor) {
        case "top":
            return [0, -1];
        case "right":
            return [1, 0];
        case "bottom":
            return [0, 1];
        case "left":
            return [-1, 0];
        default:
            return null;
    }
}

/**
 * Точка на границе узла по лучу из центра к toward. Для центра привязки стрелка
 * должна упираться в контур, а не уходить под фигуру.
 */
export function clipToNodeBoundary(node: Pick<AnchorNode, "box" | "kind">, toward: Point): Point {
    const [cx, cy] = boxCenter(node.box);
    const dx = toward[0] - cx;
    const dy = toward[1] - cy;
    if (dx === 0 && dy === 0) return [cx, cy];
    const hw = node.box.w / 2;
    const hh = node.box.h / 2;
    if (hw <= 0 || hh <= 0) return [cx, cy];
    let t: number;
    if (node.kind === "ellipse") {
        t = 1 / Math.sqrt((dx * dx) / (hw * hw) + (dy * dy) / (hh * hh));
    } else if (node.kind === "diamond") {
        t = 1 / (Math.abs(dx) / hw + Math.abs(dy) / hh);
    } else {
        t = Math.min(dx === 0 ? Infinity : hw / Math.abs(dx), dy === 0 ? Infinity : hh / Math.abs(dy));
    }
    t = Math.min(t, 1);
    return [cx + dx * t, cy + dy * t];
}

/** Конец стрелки у узла: точка привязки, а для центра — пересечение с контуром. */
export function resolveAnchorPoint(node: Pick<AnchorNode, "box" | "kind">, anchor: Anchor, toward: Point | null): Point {
    if (anchor !== "center" || !toward) return anchorPoint(node.box, anchor);
    return clipToNodeBoundary(node, toward);
}

export interface AnchorHit {
    node: AnchorNode;
    anchor: Anchor;
    point: Point;
}

/**
 * Узел под курсором и ближайшая точка привязки. radius — в координатах холста
 * (экранные ~12px делённые на масштаб). Над узлом, но вдали от точек, — центр.
 */
export function findAnchorTarget(
    point: Point,
    nodes: AnchorNode[],
    radius: number,
    excludeKey?: string | null,
): AnchorHit | null {
    let hovered: AnchorNode | null = null;
    for (const node of nodes) {
        if (node.key === excludeKey) continue;
        if (!boxContainsPoint(node.box, point, radius)) continue;
        if (!hovered || node.z >= hovered.z) hovered = node;
    }
    if (!hovered) return null;
    let best: { anchor: Anchor; point: Point; distance: number } | null = null;
    for (const anchor of ANCHORS) {
        const candidate = anchorPoint(hovered.box, anchor);
        const distance = Math.hypot(candidate[0] - point[0], candidate[1] - point[1]);
        if (distance <= radius && (!best || distance < best.distance)) best = { anchor, point: candidate, distance };
    }
    if (best) return { node: hovered, anchor: best.anchor, point: best.point };
    if (!boxContainsPoint(hovered.box, point)) return null;
    return { node: hovered, anchor: "center", point: boxCenter(hovered.box) };
}
