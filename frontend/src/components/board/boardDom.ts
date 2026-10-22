import { boundsOfPoints, polylineMidpoint, polylinePath, shapePath, type Box } from "@/lib/board/geometry";
import { arrowHeadPolygon } from "@/lib/board/routing";
import type { Point, ShapeKind, ShapeStyle } from "@/lib/board/types";

/**
 * Разметка объектов доски, общая для React-рендера и прямой правки DOM во время
 * жестов: при перетаскивании React не перерисовывается, а эти функции двигают
 * уже существующие элементы по их data-part.
 */

/** Запас вокруг ломаной стрелки: наконечник и зона попадания не обрезаются. */
export const CONNECTOR_PAD = 18;

export interface ConnectorLayout {
    left: number;
    top: number;
    width: number;
    height: number;
    line: string;
    startHead: string;
    endHead: string;
    label: Point;
}

function polygonPath(points: Point[], offsetX: number, offsetY: number): string {
    return `${polylinePath(points, offsetX, offsetY)} Z`;
}

export function connectorLayout(points: Point[], style: Pick<ShapeStyle, "start_head" | "end_head" | "stroke_width">): ConnectorLayout {
    const bounds = boundsOfPoints(points);
    const left = bounds.x - CONNECTOR_PAD;
    const top = bounds.y - CONNECTOR_PAD;
    const last = points.length - 1;
    const startHead = style.start_head === "arrow" && points.length >= 2
        ? polygonPath(arrowHeadPolygon(points[1], points[0], style.stroke_width), left, top)
        : "";
    const endHead = style.end_head === "arrow" && points.length >= 2
        ? polygonPath(arrowHeadPolygon(points[last - 1], points[last], style.stroke_width), left, top)
        : "";
    const mid = polylineMidpoint(points);
    return {
        left,
        top,
        width: bounds.w + CONNECTOR_PAD * 2,
        height: bounds.h + CONNECTOR_PAD * 2,
        line: polylinePath(points, left, top),
        startHead,
        endHead,
        label: [mid[0] - left, mid[1] - top],
    };
}

function setBox(element: HTMLElement, left: number, top: number, width: number, height: number): void {
    element.style.left = `${left}px`;
    element.style.top = `${top}px`;
    element.style.width = `${width}px`;
    element.style.height = `${height}px`;
}

/** Двигает стрелку/линию по новым точкам без React. */
export function applyConnectorDom(element: HTMLElement, points: Point[], style: Pick<ShapeStyle, "start_head" | "end_head" | "stroke_width">): void {
    const layout = connectorLayout(points, style);
    setBox(element, layout.left, layout.top, layout.width, layout.height);
    const svg = element.querySelector("svg");
    if (svg) {
        svg.setAttribute("width", String(layout.width));
        svg.setAttribute("height", String(layout.height));
    }
    element.querySelectorAll<SVGPathElement>("[data-part='line'], [data-part='hit'], [data-part='halo']").forEach((path) => path.setAttribute("d", layout.line));
    element.querySelector("[data-part='head-start']")?.setAttribute("d", layout.startHead);
    element.querySelector("[data-part='head-end']")?.setAttribute("d", layout.endHead);
    const label = element.querySelector<HTMLElement>("[data-part='label']");
    if (label) {
        label.style.left = `${layout.label[0]}px`;
        label.style.top = `${layout.label[1]}px`;
    }
}

/** Отступ контура внутрь рамки на половину толщины — обводка не вылезает за bbox. */
export function shapeInset(strokeWidth: number): number {
    return strokeWidth / 2;
}

/** Двигает/меняет размер фигуры или стикера без React. */
export function applyNodeDom(element: HTMLElement, box: Box, kind: ShapeKind | "sticker", strokeWidth = 2): void {
    setBox(element, box.x, box.y, box.w, box.h);
    if (kind === "sticker") return;
    const svg = element.querySelector("svg");
    if (svg) {
        svg.setAttribute("width", String(box.w));
        svg.setAttribute("height", String(box.h));
    }
    element.querySelector("[data-part='outline']")?.setAttribute("d", shapePath(kind, box.w, box.h, shapeInset(strokeWidth)));
}
