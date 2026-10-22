import { describe, expect, it } from "vitest";
import { handleBoards, mockState, stamp, type MockState } from "../../../e2e/support/mockApi";

type Json = Record<string, unknown>;
type BatchResult = {
    shapes: Json[];
    stickers: Json[];
    deleted_shape_ids: number[];
    deleted_sticker_ids: number[];
    id_map: Record<string, number>;
};

const rect = { kind: "rect", x: 10, y: 20, w: 100, h: 80, z_index: 8 };
const arrow = { kind: "arrow", points: [[10, 20], [110, 100]], z_index: 9 };
const stickerData = { body: "New", color: "#fff19a", canvas_x: 20, canvas_y: 30, width: 230, height: 230, z_index: 10, task_ids: [110, 102, 100] };

function seededState(): MockState {
    const state = mockState();
    const base = { board_id: 1, revision: 1, created_at: stamp, updated_at: stamp };
    state.shapes.push(
        { ...base, ...rect, id: 100, points: null, start_ref: null, end_ref: null },
        { ...base, ...arrow, id: 101, x: 10, y: 20, w: 100, h: 80,
            start_ref: { type: "sticker", id: 1, anchor: "right" },
            end_ref: { type: "shape", id: 100, anchor: "left" },
            style: { fill: "green", end_head: "arrow" } },
        { ...base, ...rect, id: 102, kind: "ellipse", points: null, start_ref: null, end_ref: null },
        { ...base, ...rect, id: 103, board_id: 2 },
    );
    state.stickers.push({ ...state.stickers[0], id: 4, board_id: 2 });
    state.nextIds.shape = 200;
    return state;
}

function request(state: MockState, ops: unknown) {
    return handleBoards(state, 1, "/boards/1/batch", "POST", new URL("https://mock.test/boards/1/batch"), () => ({ ops }));
}

function content(state: MockState) {
    return structuredClone({ boards: state.boards, stickers: state.stickers, shapes: state.shapes, nextIds: state.nextIds });
}

function mixedPrefix(): Json[] {
    return [
        { op: "create_shape", client_id: "new-shape", data: rect },
        { op: "create_sticker", client_id: "new-sticker", data: stickerData },
        { op: "update_shape", id: 102, revision: 1, data: { label: "Updated", z_index: 30 } },
        { op: "update_sticker", id: 2, revision: 1, data: { ...stickerData, body: "Updated" } },
        { op: "delete_shape", id: 100, revision: 1 },
        { op: "delete_sticker", id: 1, revision: 1 },
        { op: "move_sticker", id: 3, data: { canvas_x: 900, z_index: 40 } },
    ];
}

function expectRollback(state: MockState, ops: unknown, status: number) {
    const before = content(state);
    const originalStickers = state.stickers;
    const originalShapes = state.shapes;
    const originalIds = state.nextIds;
    const originalArrow = state.shapes.find(shape => shape.id === 101);
    expect(request(state, ops).status).toBe(status);
    expect(content(state)).toEqual(before);
    expect(state.stickers).toBe(originalStickers);
    expect(state.shapes).toBe(originalShapes);
    expect(state.nextIds).toBe(originalIds);
    expect(state.shapes.find(shape => shape.id === 101)).toBe(originalArrow);
}

describe("mock board batch transactions", () => {
    it.each([
        ["sticker update conflict", { op: "update_sticker", id: 3, revision: 999, data: stickerData }, 409],
        ["sticker delete conflict", { op: "delete_sticker", id: 3, revision: 999 }, 409],
        ["shape update conflict", { op: "update_shape", id: 102, revision: 1, data: { label: "Conflict" } }, 409],
        ["shape delete conflict", { op: "delete_shape", id: 102, revision: 1 }, 409],
        ["missing shape update", { op: "update_shape", id: 999, data: { label: "Missing" } }, 404],
        ["missing shape delete", { op: "delete_shape", id: 999 }, 404],
        ["foreign shape delete", { op: "delete_shape", id: 103 }, 404],
        ["missing sticker move", { op: "move_sticker", id: 999, data: { canvas_x: 100 } }, 404],
        ["foreign sticker move", { op: "move_sticker", id: 4, data: { canvas_x: 100 } }, 404],
        ["invalid shape data", { op: "create_shape", data: { ...rect, label: null } }, 422],
    ])("rolls back mixed creates, updates, deletes and detached refs after late %s", (_name, last, status) => {
        expectRollback(seededState(), [...mixedPrefix(), last], status as number);
    });

    it("commits mixed create/update/delete operations, detaches refs and preserves layers", () => {
        const state = seededState();
        const response = request(state, mixedPrefix());
        expect(response.status ?? 200).toBe(200);
        const result = response.json as BatchResult;
        expect(result.id_map).toEqual({ "new-shape": 200, "new-sticker": 10 });
        expect(result.deleted_shape_ids).toEqual([100]);
        expect(result.deleted_sticker_ids).toEqual([1]);
        expect(state.shapes.find(shape => shape.id === 100)).toBeUndefined();
        expect(state.stickers.find(sticker => sticker.id === 1)).toBeUndefined();
        expect(state.shapes.find(shape => shape.id === 101)).toMatchObject({ start_ref: null, end_ref: null });
        expect(Number(state.shapes.find(shape => shape.id === 101)?.revision)).toBeGreaterThan(1);
        expect(state.shapes.find(shape => shape.id === 102)).toMatchObject({ label: "Updated", revision: 2, z_index: 30 });
        expect(state.stickers.find(sticker => sticker.id === 2)).toMatchObject({ body: "Updated", revision: 2, task_ids: [100, 102, 110] });
        expect(state.stickers.find(sticker => sticker.id === 3)).toMatchObject({ canvas_x: 900, z_index: 40 });
        expect(state.shapes.find(shape => shape.id === 103)).toMatchObject({ board_id: 2, revision: 1 });
        expect(result.shapes.find(shape => shape.id === 200)).toMatchObject({ z_index: 8 });
        expect(result.stickers.find(sticker => sticker.id === 10)).toMatchObject({ z_index: 10, task_ids: [100, 102, 110] });
    });

    it.each([
        ["sticker", "shape"],
        ["shape", "sticker"],
    ])("rejects a %s client ref mislabelled as %s even when numeric IDs overlap", (actual, wrong) => {
        const state = seededState();
        state.nextIds.shape = state.nextIds.sticker;
        expectRollback(state, [
            { op: "create_sticker", client_id: "sticker-target", data: stickerData },
            { op: "create_shape", client_id: "shape-target", data: rect },
            { op: "create_shape", data: { ...arrow, start_ref: { type: wrong, client_id: actual + "-target" } } },
        ], 422);
    });

    it.each([
        ["missing target", { type: "shape", id: 999 }],
        ["foreign shape", { type: "shape", id: 103 }],
        ["foreign sticker", { type: "sticker", id: 4 }],
        ["wrong existing type", { type: "sticker", id: 102 }],
        ["negative target", { type: "shape", id: -100 }],
        ["zero target", { type: "sticker", id: 0 }],
        ["missing client target", { type: "shape", client_id: "absent" }],
        ["missing locator", { type: "shape" }],
        ["two locators", { type: "shape", id: 102, client_id: "new-shape" }],
        ["invalid type", { type: "board", id: 1 }],
        ["invalid anchor", { type: "shape", id: 102, anchor: "outside" }],
        ["linear target", { type: "shape", id: 101 }],
        ["self target", { type: "shape", id: 101, anchor: "center" }],
    ])("rolls back a late invalid ref: %s", (_name, ref) => {
        expectRollback(seededState(), [
            ...mixedPrefix(),
            { op: "update_shape", id: 101, data: { end_ref: ref } },
        ], 422);
    });

    it.each(["shape", "sticker"])("rejects a forward %s client ref before its target is created", (type) => {
        expectRollback(seededState(), [
            { op: "create_sticker", client_id: "first", data: stickerData },
            { op: "create_shape", data: { ...arrow, end_ref: { type, client_id: "later" } } },
            { op: "create_" + type, client_id: "later", data: type === "shape" ? rect : stickerData },
        ], 422);
    });

    it("rejects a ref to an object deleted earlier in the batch", () => {
        expectRollback(seededState(), [
            { op: "delete_shape", id: 100, revision: 1 },
            { op: "create_shape", data: { ...arrow, end_ref: { type: "shape", id: 100 } } },
        ], 422);
    });

    it.each([
        ["create_shape", "create_shape"],
        ["create_sticker", "create_sticker"],
        ["create_shape", "create_sticker"],
        ["create_sticker", "create_shape"],
    ])("uses one client_id namespace for %s and %s", (first, second) => {
        expectRollback(seededState(), [
            { op: first, client_id: "same", data: first === "create_shape" ? rect : stickerData },
            { op: second, client_id: "same", data: second === "create_shape" ? rect : stickerData },
        ], 422);
    });

    it.each([undefined, null, [], {}, "ops", [{ op: "unknown" }]])("rejects malformed or empty ops %j", (ops) => {
        expectRollback(seededState(), ops, 422);
    });

    it.each(["", "x".repeat(65)])("rejects an invalid create client_id length", (clientId) => {
        expectRollback(seededState(), [{ op: "create_sticker", client_id: clientId, data: stickerData }], 422);
    });

    it("accepts 500 operations and rejects 501 without mutations", () => {
        const ops = Array.from({ length: 500 }, (_, index) => ({ op: "move_sticker", id: 3, data: { z_index: index } }));
        const state = seededState();
        expect(request(state, ops).status ?? 200).toBe(200);
        expect(state.stickers.find(sticker => sticker.id === 3)?.z_index).toBe(499);
        expectRollback(seededState(), [...ops, ops[0]], 422);
    });

    it("resolves earlier shape and sticker client refs on create and partial update", () => {
        const state = seededState();
        const response = request(state, [
            { op: "create_sticker", client_id: "sticker-target", data: stickerData },
            { op: "create_shape", client_id: "shape-target", data: rect },
            { op: "create_shape", client_id: "connector", data: {
                ...arrow,
                start_ref: { type: "shape", client_id: "shape-target", anchor: "right" },
                end_ref: { type: "sticker", client_id: "sticker-target" },
            } },
            { op: "update_shape", id: 101, revision: 1, data: {
                start_ref: { type: "sticker", client_id: "sticker-target", anchor: "top" },
                end_ref: { type: "shape", client_id: "shape-target", anchor: "bottom" },
                style: { stroke: "red" }, z_index: 70,
            } },
        ]);
        expect(response.status ?? 200).toBe(200);
        const result = response.json as BatchResult;
        expect(result.id_map).toEqual({ "sticker-target": 10, "shape-target": 200, connector: 201 });
        expect(result.shapes.find(shape => shape.id === 201)).toMatchObject({
            start_ref: { type: "shape", id: 200, anchor: "right" },
            end_ref: { type: "sticker", id: 10, anchor: "center" },
            style: { end_head: "arrow" },
        });
        expect(result.shapes.find(shape => shape.id === 101)).toMatchObject({
            revision: 2, z_index: 70,
            start_ref: { type: "sticker", id: 10, anchor: "top" },
            end_ref: { type: "shape", id: 200, anchor: "bottom" },
            style: { fill: "green", stroke: "red", end_head: "arrow" },
        });
        expect(request(state, [{ op: "update_shape", id: 101, revision: 2, data: {
            start_ref: { type: "shape", id: 102 }, end_ref: { type: "sticker", id: 2 },
        } }]).status ?? 200).toBe(200);
        expect(state.shapes.find(shape => shape.id === 101)).toMatchObject({
            revision: 3, start_ref: { type: "shape", id: 102, anchor: "center" },
            end_ref: { type: "sticker", id: 2, anchor: "center" },
        });
        expect(request(state, [{ op: "update_shape", id: 101, revision: 3, data: { end_ref: null } }]).status ?? 200).toBe(200);
        expect(state.shapes.find(shape => shape.id === 101)?.end_ref).toBeNull();
    });

    it("does not treat detached refs as revision conflicts within the same batch", () => {
        const state = seededState();
        const response = request(state, [
            { op: "delete_shape", id: 100, revision: 1 },
            { op: "update_shape", id: 101, revision: 1, data: { label: "Detached once" } },
            { op: "update_shape", id: 101, revision: 2, data: { label: "Detached twice" } },
        ]);
        expect(response.status ?? 200).toBe(200);
        expect(state.shapes.find(shape => shape.id === 101)).toMatchObject({
            end_ref: null, revision: 4, label: "Detached twice",
        });
    });

    it("allows a shape without client_id and safely maps prototype-like client IDs", () => {
        const state = seededState();
        const response = request(state, [
            { op: "create_shape", data: rect },
            { op: "create_shape", client_id: "__proto__", data: rect },
            { op: "create_shape", client_id: "toString", data: { ...arrow, end_ref: { type: "shape", client_id: "__proto__" } } },
        ]);
        expect(response.status ?? 200).toBe(200);
        const result = response.json as BatchResult;
        expect(Object.keys(result.id_map)).toEqual(["__proto__", "toString"]);
        expect(result.id_map.__proto__).toBe(201);
        expect(result.shapes.find(shape => shape.id === 202)?.end_ref).toEqual({ type: "shape", id: 201, anchor: "center" });
    });

    it("sorts numeric task IDs for direct sticker create and update without mutating request data", () => {
        const state = seededState();
        const data = { ...stickerData, task_ids: [110, 102, 100, 102] };
        const create = handleBoards(state, 1, "/boards/1/stickers", "POST", new URL("https://mock.test"), () => data);
        expect((create.json as Json).task_ids).toEqual([100, 102, 110]);
        const update = handleBoards(state, 1, "/boards/1/stickers/2", "PATCH", new URL("https://mock.test"), () => data);
        expect((update.json as Json).task_ids).toEqual([100, 102, 110]);
        expect(data.task_ids).toEqual([110, 102, 100, 102]);
    });
});
