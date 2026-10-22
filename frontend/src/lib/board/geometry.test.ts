import { describe, expect, it } from "vitest";
import { anchorPoint, clipToNodeBoundary, findAnchorTarget, type AnchorNode } from "@/lib/board/anchors";
import {
    boundsOfPoints,
    boxFromDrag,
    boxesIntersect,
    constrainAngle,
    distanceToPolyline,
    isBoxVisible,
    polylineMidpoint,
    shapePath,
    unionBoxes,
} from "@/lib/board/geometry";
import { objectsInMarquee } from "@/lib/board/hit";
import { arrowHeadPolygon, routeConnector, simplifyPolyline } from "@/lib/board/routing";
import { resizeBox, snapMove, snapPoint, snapResize } from "@/lib/board/snapping";

const box = { x: 100, y: 100, w: 200, h: 100 };

describe("геометрия", () => {
    it("рамка по протяжке в любую сторону и квадрат с Shift", () => {
        expect(boxFromDrag([10, 10], [0, 30])).toEqual({ x: 0, y: 10, w: 10, h: 20 });
        expect(boxFromDrag([10, 10], [40, 20], true)).toEqual({ x: 10, y: 10, w: 30, h: 30 });
        expect(boxFromDrag([10, 10], [-20, 15], true)).toEqual({ x: -20, y: 10, w: 30, h: 30 });
    });

    it("угол 45° с Shift", () => {
        const [x, y] = constrainAngle([0, 0], [100, 10]);
        expect(y).toBeCloseTo(0);
        expect(x).toBeCloseTo(Math.hypot(100, 10));
        const [dx, dy] = constrainAngle([0, 0], [50, 45]);
        expect(dx).toBeCloseTo(dy);
    });

    it("объединение, пересечение, видимость", () => {
        expect(unionBoxes([box, { x: 0, y: 0, w: 10, h: 10 }])).toEqual({ x: 0, y: 0, w: 300, h: 200 });
        expect(unionBoxes([])).toBeNull();
        expect(boxesIntersect(box, { x: 290, y: 190, w: 5, h: 5 })).toBe(true);
        expect(boxesIntersect(box, { x: 400, y: 190, w: 5, h: 5 })).toBe(false);
        expect(isBoxVisible({ x: 1100, y: 0, w: 10, h: 10 }, { x: 0, y: 0, w: 1000, h: 800 }, 200)).toBe(true);
        expect(isBoxVisible({ x: 1500, y: 0, w: 10, h: 10 }, { x: 0, y: 0, w: 1000, h: 800 }, 200)).toBe(false);
    });

    it("середина ломаной и расстояние до неё", () => {
        expect(polylineMidpoint([[0, 0], [100, 0], [100, 100]])).toEqual([100, 0]);
        expect(polylineMidpoint([[0, 0], [10, 0]])).toEqual([5, 0]);
        expect(distanceToPolyline([50, 10], [[0, 0], [100, 0]])).toBe(10);
        expect(boundsOfPoints([[5, 7], [-5, 20]])).toEqual({ x: -5, y: 7, w: 10, h: 13 });
    });

    it("контуры фигур строятся для всех видов", () => {
        expect(shapePath("rect", 100, 50, 1)).toMatch(/^M /);
        expect(shapePath("ellipse", 100, 50)).toContain("A 50 25");
        expect(shapePath("diamond", 100, 50)).toBe("M 50 0 L 100 25 L 50 50 L 0 25 Z");
    });
});

describe("точки привязки", () => {
    const nodes: AnchorNode[] = [
        { key: "s1", kind: "sticker", box, z: 0 },
        { key: "f2", kind: "rect", box: { x: 150, y: 120, w: 50, h: 50 }, z: 5 },
    ];

    it("координаты пяти точек", () => {
        expect(anchorPoint(box, "top")).toEqual([200, 100]);
        expect(anchorPoint(box, "right")).toEqual([300, 150]);
        expect(anchorPoint(box, "bottom")).toEqual([200, 200]);
        expect(anchorPoint(box, "left")).toEqual([100, 150]);
        expect(anchorPoint(box, "center")).toEqual([200, 150]);
    });

    it("прилипает к ближайшей точке в радиусе, иначе центр узла", () => {
        expect(findAnchorTarget([295, 152], nodes, 12)).toMatchObject({ anchor: "right", node: { key: "s1" } });
        expect(findAnchorTarget([250, 180], nodes, 12)).toMatchObject({ anchor: "center", node: { key: "s1" } });
        expect(findAnchorTarget([500, 500], nodes, 12)).toBeNull();
    });

    it("верхний узел выигрывает, исключённый пропускается", () => {
        expect(findAnchorTarget([176, 145], nodes, 4)).toMatchObject({ node: { key: "f2" }, anchor: "center" });
        expect(findAnchorTarget([176, 145], nodes, 4, "f2")).toMatchObject({ node: { key: "s1" } });
    });

    it("центр привязки упирается в контур фигуры", () => {
        expect(clipToNodeBoundary({ kind: "rect", box }, [500, 150])).toEqual([300, 150]);
        const [ex, ey] = clipToNodeBoundary({ kind: "ellipse", box }, [200, 500]);
        expect(ex).toBeCloseTo(200);
        expect(ey).toBeCloseTo(200);
        const [dx, dy] = clipToNodeBoundary({ kind: "diamond", box }, [500, 150]);
        expect([dx, dy]).toEqual([300, 150]);
    });
});

describe("маршрут стрелки", () => {
    it("прямой — один отрезок", () => {
        expect(routeConnector([0, 0], [100, 50], "straight")).toEqual([[0, 0], [100, 50]]);
    });

    it("ортогональный: три сегмента для одной оси, два — для разных", () => {
        expect(routeConnector([0, 0], [100, 50], "orthogonal", "right", "left")).toEqual([[0, 0], [50, 0], [50, 50], [100, 50]]);
        expect(routeConnector([0, 0], [100, 50], "orthogonal", "right", "top")).toEqual([[0, 0], [100, 0], [100, 50]]);
        expect(routeConnector([0, 0], [100, 50], "orthogonal", "bottom", "left")).toEqual([[0, 0], [0, 50], [100, 50]]);
        // без привязок — по преобладающей оси
        expect(routeConnector([0, 0], [40, 100], "orthogonal")).toEqual([[0, 0], [0, 50], [40, 50], [40, 100]]);
        // на одной линии — просто отрезок
        expect(routeConnector([0, 0], [0, 100], "orthogonal", "bottom", "top")).toEqual([[0, 0], [0, 100]]);
    });

    it("упрощение убирает дубли и точки на прямой", () => {
        expect(simplifyPolyline([[0, 0], [0, 0], [10, 0], [20, 0], [20, 5]])).toEqual([[0, 0], [20, 0], [20, 5]]);
    });

    it("наконечник — треугольник с вершиной в конце", () => {
        const head = arrowHeadPolygon([0, 0], [100, 0], 2);
        expect(head[0]).toEqual([100, 0]);
        expect(head[1][0]).toBeLessThan(100);
        expect(head[1][1]).toBeCloseTo(-head[2][1]);
    });
});

describe("прилипание и ресайз", () => {
    const others = [{ x: 300, y: 300, w: 100, h: 100 }];

    it("к сетке 8px, если соседей рядом нет", () => {
        expect(snapPoint([13, 21])).toEqual([16, 24]);
        const { box: snapped, guides } = snapMove({ x: 13, y: 21, w: 50, h: 50 }, others, 6);
        expect(snapped).toMatchObject({ x: 16, y: 24 });
        expect(guides).toHaveLength(0);
    });

    it("к краю и центру соседа с направляющей", () => {
        const { box: snapped, guides } = snapMove({ x: 303, y: 100, w: 50, h: 50 }, others, 6);
        expect(snapped.x).toBe(300);
        expect(guides[0]).toMatchObject({ axis: "x", pos: 300 });
        const centered = snapMove({ x: 327, y: 100, w: 50, h: 50 }, others, 6);
        expect(centered.box.x + 25).toBe(350);
    });

    it("ручки меняют нужные края, лимиты держат размер", () => {
        const limits = { minW: 160, minH: 160, maxW: 520, maxH: 520 };
        const origin = { x: 0, y: 0, w: 200, h: 200 };
        expect(resizeBox(origin, "se", 50, 20, limits)).toEqual({ x: 0, y: 0, w: 250, h: 220 });
        expect(resizeBox(origin, "nw", 100, 100, limits)).toEqual({ x: 40, y: 40, w: 160, h: 160 });
        expect(resizeBox(origin, "e", 1000, 0, limits).w).toBe(520);
        expect(resizeBox({ x: 0, y: 0, w: 200, h: 100 }, "se", 100, 0, { minW: 1, minH: 1, maxW: 1000, maxH: 1000 }, true)).toEqual({ x: 0, y: 0, w: 300, h: 150 });
    });

    it("тянутый край прилипает к соседу, противоположный стоит", () => {
        const limits = { minW: 8, minH: 8, maxW: 1000, maxH: 1000 };
        const { box: snapped } = snapResize({ x: 200, y: 200, w: 97, h: 50 }, "e", others, 6, limits);
        expect(snapped).toEqual({ x: 200, y: 200, w: 100, h: 50 });
        const { box: west } = snapResize({ x: 5, y: 0, w: 95, h: 50 }, "w", [], 6, limits);
        expect(west).toEqual({ x: 8, y: 0, w: 92, h: 50 });
    });
});

describe("выделение рамкой", () => {
    it("захватывает всё, что пересекает рамку, включая стикеры", () => {
        const objects = [
            { key: "s1", box: { x: 0, y: 0, w: 100, h: 100 } },
            { key: "f1", box: { x: 150, y: 150, w: 10, h: 10 } },
            { key: "f2", box: { x: 500, y: 500, w: 10, h: 10 } },
        ];
        expect(objectsInMarquee({ x: 50, y: 50, w: 120, h: 120 }, objects)).toEqual(["s1", "f1"]);
    });
});
