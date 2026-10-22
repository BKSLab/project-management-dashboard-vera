import { describe, expect, it } from "vitest";
import { scene, shape, sticker } from "@/lib/board/editorFixtures.test-support";
import { changeConnectorEndpoint, editConnectorBend } from "@/lib/board/connectorEditing";
import { connectorPoints, nodeLookup, type ShapeObject } from "@/lib/board/scene";
import type { Point } from "@/lib/board/types";

function arrow(points: Point[], orthogonal = false): ShapeObject {
    return { ...shape("f10", 0, 0, 100, 100, "arrow"), points,
        style: { ...shape("f10").style, route: orthogonal ? "orthogonal" : "straight", end_head: "arrow" },
        startRef: { type: "shape", key: "f1", anchor: "right" },
        endRef: { type: "sticker", key: "s7", anchor: "left" }, label: "Успешно" };
}

describe("editable connector routes", () => {
    it("keeps manual bends while a linked node moves", () => {
        const object = arrow([[100, 50], [300, 50], [300, 215], [500, 215]], true);
        const points = connectorPoints(object, nodeLookup(scene(shape("f1", 0, 80, 100, 100), sticker(7, 500, 100))));
        expect(points).toEqual([[100, 130], [300, 130], [300, 215], [500, 215]]);
        expect(object.points).toEqual([[100, 50], [300, 50], [300, 215], [500, 215]]);
    });

    it("moves the full custom route when both attached endpoints translate equally", () => {
        const object = arrow([[100, 50], [300, 50], [300, 215], [500, 215]], true);
        expect(connectorPoints(object, nodeLookup(scene(shape("f1", 40, 20, 100, 100), sticker(7, 540, 120)))))
            .toEqual([[140, 70], [340, 70], [340, 235], [540, 235]]);
    });

    it("adds a bend without changing links, label or line style", () => {
        const object = arrow([[0, 0], [100, 0]]);
        const changed = editConnectorBend(object, 0, [50, 30], true);
        expect(changed.points).toEqual([[0, 0], [50, 30], [100, 0]]);
        expect(changed.startRef).toBe(object.startRef);
        expect(changed.endRef).toBe(object.endRef);
        expect(changed.style).toBe(object.style);
        expect(changed.label).toBe("Успешно");
    });

    it("creates an orthogonal detour with endpoints fixed", () => {
        expect(editConnectorBend(arrow([[0, 0], [100, 0]], true), 0, [50, 30], true).points)
            .toEqual([[0, 0], [0, 30], [100, 30], [100, 0]]);
    });

    it("moves an orthogonal bend and adjacent segment without displacing endpoints", () => {
        const object = arrow([[0, 0], [50, 0], [50, 100], [100, 100]], true);
        expect(editConnectorBend(object, 1, [80, 50], false).points).toEqual([[0, 0], [80, 0], [80, 100], [100, 100]]);
    });

    it("reattaches an endpoint while preserving remaining bends", () => {
        const object = arrow([[0, 0], [50, 0], [50, 100], [100, 100]], true);
        const changed = changeConnectorEndpoint(object, "start", [0, 20], null);
        expect(changed.points).toEqual([[0, 20], [50, 20], [50, 100], [100, 100]]);
        expect(changed.startRef).toBeNull();
        expect(changed.endRef).toBe(object.endRef);
    });

    it("enforces the server point limit and refuses endpoint edits through a bend handle", () => {
        const object = arrow(Array.from({ length: 50 }, (_, i) => [i, i]));
        expect(() => editConnectorBend(object, 1, [3, 4], true)).toThrow("50");
        expect(() => editConnectorBend(object, 0, [3, 4], false)).toThrow();
    });
});


it("keeps a UI-created orthogonal detour orthogonal after another bend drag", () => {
    const original = arrow([[0, 0], [50, 0], [50, 100], [100, 100]], true);
    const detour = editConnectorBend(original, 0, [25, -20], true);
    const changed = editConnectorBend(detour, 2, [70, -40], false);
    expect(changed.points).toEqual([[0, 0], [0, -40], [70, -40], [70, 0], [70, 100], [100, 100]]);
    expect(changed.points!.every((point, i, points) => i === 0 || point[0] === points[i - 1][0] || point[1] === points[i - 1][1])).toBe(true);
    expect(changed.startRef).toBe(original.startRef);
    expect(changed.endRef).toBe(original.endRef);
});

it("moves endpoint-adjacent collinear chains without diagonal segments", () => {
    const original = arrow([[100, 50], [300, 50], [300, 100], [300, 215], [500, 215]], true);
    const changed = changeConnectorEndpoint(original, "end", [520, 235], null);
    const points = connectorPoints(changed, nodeLookup(scene(shape("f1", 0, 0, 100, 100))));
    expect(points.every((point, i) => i === 0 || point[0] === points[i - 1][0] || point[1] === points[i - 1][1])).toBe(true);
});
