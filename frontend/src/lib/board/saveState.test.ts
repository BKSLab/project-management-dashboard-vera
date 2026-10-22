import { expect, it, vi } from "vitest";
import { sticker, scene } from "@/lib/board/editorFixtures.test-support";
import { IdRegistry } from "@/lib/board/scene";
import { SaveQueue } from "@/lib/board/saveQueue";

it("reports pending from debounce through the actual in-flight response", async () => {
    const note = sticker();
    const current = scene(note);
    const registry = new IdRegistry();
    registry.bind(note.key, note.id);
    const states: boolean[] = [];
    let release = () => {};
    let entered = () => {};
    const gate = new Promise<void>(resolve => { release = resolve; });
    const started = new Promise<void>(resolve => { entered = resolve; });
    const queue = new SaveQueue({
        getScene: () => current, registry, onFailure: vi.fn(),
        onStateChange: state => states.push(state.pending),
        send: async () => {
            entered();
            await gate;
            return { shapes: [], stickers: [note.sticker], deleted_shape_ids: [], id_map: {} };
        },
    });
    current.set(note.key, { ...note, x: note.x + 10 });
    queue.markDirty([note.key]);
    const flushing = queue.flushNow();
    await started;
    expect(queue.pending).toBe(true);
    expect(states.every(pending => pending)).toBe(true);
    release();
    await flushing;
    expect(queue.pending).toBe(false);
    expect(states.at(-1)).toBe(false);
});
