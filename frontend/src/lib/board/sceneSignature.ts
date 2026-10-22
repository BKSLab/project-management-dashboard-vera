import type { Scene } from "@/lib/board/scene";

/** Содержимое без серверных ревизий и времени: собственное сохранение не создаёт лишний шаг истории. */
export function sceneSignature(scene: Scene): string {
    return JSON.stringify([...scene.values()].sort((a,b) => a.key.localeCompare(b.key)).map(object =>
        object.type === "shape" ? object : {
            type: object.type, key: object.key, x: object.x, y: object.y, w: object.w, h: object.h, z: object.z,
            body: object.sticker.body, color: object.sticker.color, task_ids: [...object.sticker.task_ids].sort((a, b) => a - b),
        },
    ));
}
