import { describe, expect, it } from "vitest";
import { scene, shape, sticker } from "@/lib/board/editorFixtures.test-support";
import { findBoardObjects } from "@/lib/board/search";

describe("board text search", () => {
    it("matches stickers, labels and arrows with Russian case and е/ё equivalence", () => {
        const note = sticker();
        note.sticker.body = "Согласование платёжного поручения";
        const block = { ...shape("f2"), label: "ПЛАТЕЖНЫЙ шлюз" };
        const arrow = { ...shape("f3", 100, 100, 100, 10, "arrow"), label: "Ошибка платежа" };
        expect(findBoardObjects(scene(note, block, arrow), "  ПЛАТЕЖ  ").map(hit => hit.key)).toEqual(["s1", "f2", "f3"]);
        expect(findBoardObjects(scene(note, block, arrow), "ошибка")[0].kind).toBe("Стрелка");
    });
    it("finds objects outside the viewport and includes the match in long text", () => {
        const far = { ...shape("f10", 100000, 100000), label: "Начало ".repeat(80) + "РЕПОЗИТОРИЙ " + "окончание ".repeat(80) };
        const [hit] = findBoardObjects(scene(far), "репозиторий");
        expect(hit.text).toContain("РЕПОЗИТОРИЙ");
        expect(hit.text.startsWith("…")).toBe(true);
        expect(hit.text.length).toBeLessThan(180);
    });
    it("does not return objects for an empty query or missing text", () => {
        expect(findBoardObjects(scene(shape("f1")), " ")).toEqual([]);
        expect(findBoardObjects(scene(shape("f1")), "нет такого")).toEqual([]);
    });
});
