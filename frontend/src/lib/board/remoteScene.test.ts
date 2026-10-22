import { describe, expect, it, vi } from "vitest";
import { scene, shape, sticker } from "@/lib/board/editorFixtures.test-support";
import { reconcileRemoteScene } from "@/lib/board/remoteScene";
import { IdRegistry, type SceneObject } from "@/lib/board/scene";
import { SaveQueue } from "@/lib/board/saveQueue";
import type { BatchOp } from "@/lib/board/types";

describe("remote scene synchronization", () => {
    it("takes a sticker revision and author metadata while another object changes", async () => {
        const first = sticker(1);
        const second = shape("f2");
        const refreshed = {
            ...first,
            sticker: { ...first.sticker, revision: 2, updated_at: "later", created_by_display_name_snapshot: "Автор обновлён" },
        };
        const result = reconcileRemoteScene(scene(first, second), scene(refreshed, { ...second, label: "Новый текст" }));
        expect(result.changes.size).toBe(1);
        expect(result.changes.has(first.key)).toBe(false);
        expect(result.base.get(first.key)).toBe(refreshed);
        expect(first.sticker.revision).toBe(1);

        let current = new Map(result.base);
        for (const [key, object] of result.changes) if (object) current.set(key, object);
        const registry = new IdRegistry();
        registry.bind(first.key, first.id);
        const send = vi.fn(async (ops: BatchOp[]) => {
            const op = ops[0];
            if (op.op !== "update_sticker") throw new Error("Expected a sticker update");
            expect(op.revision).toBe(2);
            return { shapes: [], stickers: [], deleted_shape_ids: [], id_map: {} };
        });
        const queue = new SaveQueue({ getScene: () => current, registry, send, onFailure: vi.fn() });
        current = new Map(current).set(first.key, { ...refreshed, sticker: { ...refreshed.sticker, body: "Моя правка" } });
        queue.markDirty([first.key]);
        await queue.dispose();
        expect(send).toHaveBeenCalledTimes(1);
    });

    it("does not create undo changes for revision-only updates", () => {
        const original = sticker();
        const updated = { ...original, sticker: { ...original.sticker, revision: 9, task_ids: [...original.sticker.task_ids].reverse() } };
        const result = reconcileRemoteScene(scene(original), scene(updated));
        expect(result.changes.size).toBe(0);
        expect(result.base.get(original.key)).toBe(updated);
    });

    it("keeps additions, removals and text edits as one content delta", () => {
        const original = sticker();
        const node = shape("f2");
        const added = shape("f3");
        const result = reconcileRemoteScene(scene(original, node), scene({ ...original, sticker: { ...original.sticker, body: "Чужая правка" } }, added));
        expect([...result.changes.keys()].sort()).toEqual(["f2", "f3", "s1"]);
        expect(result.changes.get("f2")).toBeNull();
        expect((result.changes.get("s1") as SceneObject)?.type).toBe("sticker");
        expect(result.base.get(original.key)).toBe(original);
    });
});
