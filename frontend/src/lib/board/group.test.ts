import { describe, expect, it } from "vitest";
import { editableSelection, expandGroupSelection, groupSelection, pruneGrouping, setSelectionLocked, ungroupSelection } from "./group";
import { scene, shape, sticker } from "./editorFixtures.test-support";

describe("explicit grouping", () => {
    const source = scene(shape("a"), shape("b"), sticker());
    const empty = { groups: [], locked: [] };
    it("groups mixed selection and expands a hit on any member", () => {
        const next = groupSelection(source, empty, ["a", "s1"], "  Связка  ", "g");
        expect(next.groups[0].name).toBe("Связка");
        expect([...expandGroupSelection(["s1"], next.groups)]).toEqual(["s1", "a"]);
        expect(empty.groups).toEqual([]);
    });
    it("merges groups without creating overlapping membership", () => {
        const first = groupSelection(source, empty, ["a", "b"], "Первая", "g");
        const next = groupSelection(source, first, ["a", "s1"], "Все", "g2");
        expect(next.groups).toHaveLength(1);
        expect(new Set(next.groups[0].members)).toEqual(new Set(["a", "b", "s1"]));
    });
    it("locks/unlocks all group members and guards every mutation", () => {
        const grouped = groupSelection(source, empty, ["a", "s1"], "Группа", "g");
        const locked = setSelectionLocked(grouped, ["s1"], true);
        expect(new Set(locked.locked)).toEqual(new Set(["s1", "a"]));
        expect(editableSelection(source, locked, ["a", "b"]).size).toBe(0);
        expect(() => ungroupSelection(locked, ["a"])).toThrow("разблокируйте");
        expect(() => groupSelection(source, locked, ["a", "b"], "Новая", "g2")).toThrow();
        expect(setSelectionLocked(locked, ["a"], false).locked).toEqual([]);
    });
    it("ungroups only touched groups and prunes deleted objects", () => {
        const grouped = groupSelection(source, empty, ["a", "s1"], "Группа", "g");
        expect(ungroupSelection(grouped, ["b"]).groups).toHaveLength(1);
        expect(ungroupSelection(grouped, ["s1"]).groups).toEqual([]);
        expect(pruneGrouping({ ...grouped, locked: ["a", "s1"] }, scene(shape("a"))))
            .toEqual({ groups: [], locked: ["a"] });
    });
    it("rejects empty names, duplicate IDs and fewer than two real objects", () => {
        expect(() => groupSelection(source, empty, ["missing", "a"], "Г", "g")).toThrow();
        expect(() => groupSelection(source, empty, ["a", "b"], " ", "g")).toThrow();
        const grouped = groupSelection(source, empty, ["a", "b"], "Г", "g");
        expect(() => groupSelection(source, grouped, ["a", "b"], "Новая", "g")).not.toThrow();
    });
});
