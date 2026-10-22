import { describe, expect, it } from "vitest";
import { buildMoveTarget, moveDeniedHint, moveLossesText, moveOptions, moveTargetQuery } from "./taskMove";

describe("перенос проектных и разовых задач", () => {
    it("строит цель и параметры предпросмотра", () => {
        expect(buildMoveTarget("PROJECT", { projectId: null, stageId: null })).toBeNull();
        expect(buildMoveTarget("PERSONAL", { projectId: null, stageId: null })).toEqual({ personal: true });
        const target = buildMoveTarget("PROJECT", { projectId: 2, stageId: 7, removeOutsiders: true })!;
        expect(target).toEqual({ project_id: 2, stage_id: 7, remove_outsiders: true });
        expect(moveTargetQuery(target)).toBe("project_id=2&stage_id=7&remove_outsiders=true");
    });
    it("исключает текущее место и объясняет права постановщика", () => {
        expect(moveOptions({ project_id: 1 }, "PROJECT", [{ id: 1 }, { id: 2 }]).projects).toEqual([{ id: 2 }]);
        expect(moveOptions({ project_id: null }, "PERSONAL", []).personal).toBe(false);
        expect(moveDeniedHint("PERSONAL", true, false)).toMatch(/постановщик/);
        expect(moveDeniedHint("PERSONAL", true, true)).toBeUndefined();
    });
    it("включает размещение ИСР в последствия переноса", () => {
        expect(moveLossesText({ dependencies: 2, document_links: 1, risks: 5, board_stickers: 0, wbs_placements: 1 })).toBe("2 зависимости, 1 связь с документом, 5 рисков, 1 размещение в ИСР");
    });
});
