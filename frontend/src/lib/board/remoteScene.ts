import type { Scene, SceneObject } from "@/lib/board/scene";
import { sceneSignature } from "@/lib/board/sceneSignature";

/** Refresh server metadata separately from changes that belong in undo history. */
export function reconcileRemoteScene(current: Scene, remote: Scene): {
    base: Scene;
    changes: Map<string, SceneObject | null>;
} {
    const base = new Map(current);
    const changes = new Map<string, SceneObject | null>();
    for (const key of new Set([...current.keys(), ...remote.keys()])) {
        const before = current.get(key);
        const after = remote.get(key);
        const beforeSignature = sceneSignature(new Map(before ? [[key, before]] : []));
        const afterSignature = sceneSignature(new Map(after ? [[key, after]] : []));
        if (beforeSignature !== afterSignature) {
            changes.set(key, after ?? null);
        } else if (after) {
            // revision, author and timestamps must advance even if another object
            // caused this refresh. These updates are not a separate user action.
            base.set(key, after);
        }
    }
    return { base, changes };
}
