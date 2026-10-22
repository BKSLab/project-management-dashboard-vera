import { describe, expect, it } from "vitest";
import { alignObjects, distributeObjects } from "./layout";
import { scene, shape, sticker } from "./editorFixtures.test-support";
import type { BoardGrouping } from "./group";

describe("board layout", () => {
    it.each([
        ["left", 20, 20], ["center", 70, 20], ["right", 120, 20],
        ["top", 20, 20], ["middle", 20, 110], ["bottom", 20, 200],
    ] as const)("aligns %s by the union of varied dimensions", (alignment, x, y) => {
        const source = scene(shape("a", 20, 20, 100, 80), shape("b", 100, 100, 120, 180));
        const result = alignObjects(source, ["a", "b"], alignment);
        const a = result.get("a") ?? source.get("a")!;
        expect([a.x, a.y]).toEqual([x, y]);
        expect(source.get("a")!.x).toBe(20);
    });
    it("aligns stickers with shapes, without modifying sticker payloads", () => {
        const source = scene(shape("a"), sticker(1, 500, 100));
        const result = alignObjects(source, ["a", "s1"], "left");
        expect(result.get("s1")!.x).toBe(0);
        expect(source.get("s1")!.x).toBe(500);
        expect(result.get("s1")).toMatchObject({ sticker: { canvas_x: 500 } });
    });
    it("distributes equal gaps with varied widths, keeping endpoints", () => {
        const source = scene(shape("a", 0, 0, 100), shape("b", 160, 40, 50), shape("c", 500, 80, 200));
        const result = distributeObjects(source, ["c", "b", "a"], "horizontal");
        expect(result.size).toBe(1);
        expect(result.get("b")!.x).toBe(275);
        expect(result.get("b")!.y).toBe(40);
    });
    it("supports vertical distribution and deterministic ties", () => {
        const source = scene(shape("a", 0, 0, 80, 100), shape("b", 0, 170, 80, 50), shape("c", 0, 500, 80, 200));
        expect(distributeObjects(source, ["a", "b", "c"], "vertical").get("b")!.y).toBe(275);
    });
    it("moves an explicit group as one unit", () => {
        const source = scene(shape("a", 100, 20), shape("b", 250, 30), shape("c", 10, 60));
        const state: BoardGrouping = { groups: [{ id: "g", name: "Группа", members: ["a", "b"] }], locked: [] };
        const result = alignObjects(source, ["a", "c"], "left", state);
        expect(result.get("a")!.x).toBe(10);
        expect(result.get("b")!.x).toBe(160);
        expect(result.get("b")!.y).toBe(30);
    });
    it("does not move groups with any locked member", () => {
        const source = scene(shape("a", 100), shape("b", 250), shape("c", 10));
        const state: BoardGrouping = { groups: [{ id: "g", name: "Группа", members: ["a", "b"] }], locked: ["b"] };
        expect(alignObjects(source, ["a", "c"], "left", state).size).toBe(0);
    });
    it("moves free connector points and syncs attached arrows atomically", () => {
        const arrow = { ...shape("arrow", 100, 40, 300, 0, "arrow"),
            points: [[200, 40], [400, 40]] as [number, number][],
            startRef: { type: "shape" as const, key: "a", anchor: "right" as const } };
        const source = scene(shape("a", 100), shape("b", 0, 200), arrow);
        const result = alignObjects(source, ["a", "b"], "left");
        expect(result.get("arrow")).toMatchObject({ points: [[100, 40], [400, 40]] });
        const free = { ...shape("line", 100, 200, 50, 50, "line"), points: [[100, 200], [150, 250]] as [number, number][] };
        expect(alignObjects(scene(shape("c"), free), ["c", "line"], "left").get("line"))
            .toMatchObject({ x: 0, points: [[0, 200], [50, 250]] });
    });
    it.each([false, true])("rejects indirect changes to a locked connector or its group (%s)", (grouped) => {
        const arrow = { ...shape("arrow", 200, 40, 200, 0, "arrow"),
            points: [[200, 40], [400, 40]] as [number, number][],
            startRef: { type: "shape" as const, key: "a", anchor: "right" as const } };
        const source = scene(shape("a", 100), shape("b", 0), arrow, shape("label", 600));
        const state: BoardGrouping = grouped
            ? { groups: [{ id: "g", name: "Связь", members: ["arrow", "label"] }], locked: ["label"] }
            : { groups: [], locked: ["arrow"] };
        expect(() => alignObjects(source, ["a", "b"], "left", state)).toThrow("заблокированную связь");
        expect(source.get("a")!.x).toBe(100);
        expect(source.get("arrow")).toEqual(arrow);
    });
    it("rejects a rigid group move with an external anchored endpoint", () => {
        const arrow = { ...shape("arrow", 200, 40, 300, 0, "arrow"),
            points: [[200, 40], [500, 40]] as [number, number][],
            startRef: { type: "shape" as const, key: "a", anchor: "right" as const },
            endRef: { type: "shape" as const, key: "external", anchor: "left" as const } };
        const source = scene(shape("a", 100), shape("external", 500), shape("b"), arrow);
        const state = { groups: [{ id: "g", name: "Группа", members: ["a", "arrow"] }], locked: [] };
        expect(() => alignObjects(source, ["a", "b"], "left", state)).toThrow("внешним объектом");
        expect(source.get("a")!.x).toBe(100);
        state.groups[0].members.push("external");
        const moved = alignObjects(source, ["a", "b"], "left", state);
        expect(moved.get("a")!.x).toBe(0);
        expect(moved.get("external")!.x).toBe(400);
        expect(moved.get("arrow")).toMatchObject({ points: [[100, 40], [400, 40]] });
    });
    it("rejects out-of-range derived connector endpoints instead of relying on save clamping", () => {
        const arrow = { ...shape("arrow", 999900, 40, 50, 0, "arrow"),
            points: [[999900, 40], [999950, 40]] as [number, number][],
            startRef: { type: "shape" as const, key: "a", anchor: "right" as const } };
        const source = scene(shape("a", 999800), shape("b", 1_000_000), arrow);
        expect(() => alignObjects(source, ["a", "b"], "right")).toThrow("границы доски");
        expect(source.get("a")!.x).toBe(999800);
        expect(source.get("arrow")).toEqual(arrow);
    });
    it("requires two alignment or three distribution units", () => {
        expect(alignObjects(scene(shape("a")), ["a"], "left").size).toBe(0);
        expect(distributeObjects(scene(shape("a"), shape("b")), ["a", "b"], "horizontal").size).toBe(0);
    });
    it("rejects invalid coordinates rather than corrupting the scene", () => {
        expect(() => alignObjects(scene(shape("a", NaN), shape("b")), ["a", "b"], "left")).toThrow();
    });
});
