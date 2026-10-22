import type { Scene } from "@/lib/board/scene";

export interface BoardSearchHit {
    key: string;
    kind: string;
    text: string;
}

function normalized(text: string): string {
    return text.toLocaleLowerCase("ru-RU").replaceAll("ё", "е").trim();
}

const KIND_NAMES: Record<string, string> = {
    rect: "Блок", ellipse: "Овал", diamond: "Развилка", text: "Текст",
    arrow: "Стрелка", line: "Линия", sticker: "Стикер",
};

export function findBoardObjects(scene: Scene, query: string): BoardSearchHit[] {
    const needle = normalized(query);
    if (!needle) return [];
    const hits: BoardSearchHit[] = [];
    for (const object of scene.values()) {
        const text = (object.type === "sticker" ? object.sticker.body : object.label).replace(/\s+/g, " ").trim();
        const index = normalized(text).indexOf(needle);
        if (index < 0) continue;
        const start = Math.max(0, index - 35);
        const end = Math.min(text.length, Math.max(start + 140, index + needle.length));
        hits.push({
            key: object.key,
            kind: KIND_NAMES[object.type === "sticker" ? object.type : object.kind],
            text: (start ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : ""),
        });
    }
    return hits;
}
