import { describe, expect, it } from "vitest";
import { createSelectionTemplate, instantiateTemplate, validateTemplate } from "./template";
import { scene, shape, sticker } from "./editorFixtures.test-support";

function sample() {
    const arrow = { ...shape("arrow", 100, 40, 100, 170, "arrow"),
        points: [[100, 40], [200, 215]] as [number, number][],
        startRef: { type: "shape" as const, key: "a", anchor: "right" as const },
        endRef: { type: "sticker" as const, key: "s1", anchor: "left" as const } };
    const source = scene(shape("a"), sticker(1, 200, 100), arrow);
    return createSelectionTemplate(source, source.keys(), "Схема", "template-1",
        { groups: [{ id: "old", name: "Узлы", members: ["a", "s1"] }], locked: ["s1"] });
}

describe("selection templates", () => {
    it("roundtrips through JSON without source IDs, task links or authors", () => {
        const template = sample();
        const loaded = JSON.parse(JSON.stringify(template));
        expect(() => validateTemplate(loaded)).not.toThrow();
        const note = loaded.items.find((item: { type: string }) => item.type === "sticker");
        expect(note.data.task_ids).toEqual([]);
        expect(note.data).not.toHaveProperty("id");
        expect(note.data).not.toHaveProperty("board_id");
        expect(note.data).not.toHaveProperty("created_by_user_id");
        expect(loaded.groups[0].members).toEqual(["t0", "t2"]);
    });
    it("maps arrow refs to BOTH shapes and stickers in one insertion", () => {
        let counter = 0;
        const result = instantiateTemplate(sample(), { x: 500, y: 300 }, () => `new-${counter++}`, 10);
        expect(result.operations).toHaveLength(3);
        expect(result.operations.filter((op) => op.op === "create_sticker")).toHaveLength(1);
        const arrow = result.operations.find((op) => op.op === "create_shape" && op.data.kind === "arrow")!;
        expect(arrow).toMatchObject({ data: {
            start_ref: { type: "shape", client_id: "new-0", anchor: "right" },
            end_ref: { type: "sticker", client_id: "new-2", anchor: "left" },
            points: [[600, 340], [700, 515]],
        } });
        expect(result.groups[0].members).toEqual(["new-0", "new-2"]);
        expect(result.locked).toEqual(["new-2"]);
        expect(result.groups[0].id).toBe("new-3");
    });
    it("detaches arrows from unselected nodes, keeping resolved endpoints", () => {
        const a = shape("a", 100, 50);
        const arrow = { ...shape("arrow", 0, 0, 200, 100, "arrow"),
            points: [[0, 0], [300, 200]] as [number, number][],
            startRef: { type: "shape" as const, key: "a", anchor: "right" as const } };
        const template = createSelectionTemplate(scene(a, arrow), ["arrow"], "Стрелка", "t");
        expect(template.items[0]).toMatchObject({ data: { start_ref: null, points: [[200, 90], [300, 200]] } });
    });
    it("does not preserve incomplete groups", () => {
        const source = scene(shape("a"), shape("b"));
        expect(createSelectionTemplate(source, ["a"], "Один", "t",
            { groups: [{ id: "g", name: "Два", members: ["a", "b"] }], locked: [] }).groups).toEqual([]);
    });
    it("rejects source IDs, dangling or mismatched references", () => {
        const template = sample();
        const arrow = template.items.find((item) => item.type === "shape" && item.data.kind === "arrow")!;
        if (arrow.type !== "shape") throw new Error("fixture");
        arrow.data.end_ref = { type: "shape", client_id: "t2", anchor: "left" };
        expect(() => validateTemplate(template)).toThrow();
        arrow.data.end_ref = { type: "sticker", id: 1, anchor: "left" };
        expect(() => validateTemplate(template)).toThrow();
    });
    it("rejects duplicate IDs, external task links and overlapping groups", () => {
        const template = sample();
        template.items[1].client_id = template.items[0].client_id;
        expect(() => validateTemplate(template)).toThrow();
        const linked = sample();
        const note = linked.items.find((item) => item.type === "sticker")!;
        if (note.type !== "sticker") throw new Error("fixture");
        note.data.task_ids = [1];
        expect(() => validateTemplate(linked)).toThrow();
        const overlap = sample();
        overlap.groups.push({ id: "other", name: "Другая", members: ["t0", "t1"] });
        expect(() => validateTemplate(overlap)).toThrow();
    });
    it("rejects bad dimensions and translation outside board bounds", () => {
        expect(() => instantiateTemplate(sample(), { x: 1_000_000, y: 0 }, () => crypto.randomUUID(), 0)).toThrow();
        const template = sample();
        const note = template.items.find((item) => item.type === "sticker")!;
        if (note.type !== "sticker") throw new Error("fixture");
        note.data.width = 1;
        expect(() => validateTemplate(template)).toThrow();
    });
    it.each(["id", "board_id", "created_by_user_id"])("rejects hidden source field %s in a loaded template", (field) => {
        const template = sample();
        const note = template.items.find((item) => item.type === "sticker")!;
        Object.assign(note.data, { [field]: 99 });
        expect(() => validateTemplate(template)).toThrow();
        expect(() => instantiateTemplate(template, { x: 0, y: 0 }, () => crypto.randomUUID(), 0)).toThrow();
    });
    it("rejects hidden style/reference/shape properties and null text bytes", () => {
        const template = sample();
        const shape = template.items.find((item) => item.type === "shape")!;
        Object.assign(shape.data, { board_id: 99 });
        expect(() => validateTemplate(template)).toThrow();
        const broken = sample(); broken.name = String.fromCharCode(0);
        expect(() => validateTemplate(broken)).toThrow();
    });
    it("does not mutate template and requires unique new IDs", () => {
        const template = sample(), before = JSON.stringify(template);
        let next = 0;
        const result = instantiateTemplate(template, { x: 0, y: 0 }, () => `n${next++}`, 100);
        if (result.operations[0].op === "create_shape") result.operations[0].data.style.fill = "red";
        expect(JSON.stringify(template)).toBe(before);
        expect(() => instantiateTemplate(template, { x: 0, y: 0 }, () => "same", 0)).toThrow();
    });
});
