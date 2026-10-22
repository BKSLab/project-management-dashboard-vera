import { defaultStyle, type ShapeKind } from "@/lib/board/types";
import type { SceneObject, ShapeObject, StickerObject } from "@/lib/board/scene";

export function shape(key: string, x = 0, y = 0, w = 100, h = 80, kind: ShapeKind = "rect"): ShapeObject {
    return { key, type: "shape", x, y, w, h, z: 0, kind, points: null,
        startRef: null, endRef: null, style: defaultStyle(kind), label: key };
}
export function sticker(id = 1, x = 200, y = 100): StickerObject {
    return { key: `s${id}`, type: "sticker", id, x, y, w: 230, h: 230, z: 1,
        sticker: { id, project_id: 3, board_id: 4, body: "Заметка", color: "#fff19a",
            canvas_x: x, canvas_y: y, width: 230, height: 230, task_ids: [31],
            created_by_user_id: 42, created_by_username_snapshot: "author",
            created_by_display_name_snapshot: "Автор", revision: 1, created_at: "", updated_at: "" } };
}
export function scene(...objects: SceneObject[]) { return new Map(objects.map((object) => [object.key, object])); }
