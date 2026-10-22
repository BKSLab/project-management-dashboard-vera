import { boxesIntersect, type Box } from "@/lib/board/geometry";

/** Ключи объектов, которых касается рамка выделения (стикеры тоже). */
export function objectsInMarquee(marquee: Box, objects: { key: string; box: Box }[]): string[] {
    if (marquee.w < 1 && marquee.h < 1) return [];
    return objects.filter((object) => boxesIntersect(marquee, object.box)).map((object) => object.key);
}

/** Переключение объекта в выделении по Shift+клику. */
export function toggleSelection(selection: string[], key: string): string[] {
    return selection.includes(key) ? selection.filter((item) => item !== key) : [...selection, key];
}
