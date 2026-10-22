import { describe, expect, it } from "vitest";
import {
    barProgress,
    conflictingSuccessors,
    criticalState,
    isAlreadyLinked,
    progressHint,
} from "./ganttSchedule";

const task = (id: number, start: string | null, due: string | null) => ({ id, start_date: start, due_date: due });

describe("barProgress", () => {
    it("clamps and rounds, keeps unknown progress empty", () => {
        expect(barProgress(33.4)).toBe(33);
        expect(barProgress(140)).toBe(100);
        expect(barProgress(-5)).toBe(0);
        expect(barProgress(null)).toBeNull();
        expect(barProgress(undefined)).toBeNull();
        expect(progressHint(50)).toBe("Выполнено 50%");
        expect(progressHint(null)).toBe("");
    });
});

describe("criticalState", () => {
    it("highlights critical bars and dims the rest only in the mode", () => {
        expect(criticalState(true, true)).toBe("critical");
        expect(criticalState(false, true)).toBe("dimmed");
        expect(criticalState(undefined, true)).toBe("dimmed");
        expect(criticalState(true, false)).toBeNull();
    });
});

describe("conflictingSuccessors", () => {
    const tasks = new Map([
        [2, task(2, "2026-09-10", "2026-09-12")],
        [3, task(3, null, "2026-09-20")],
        [4, task(4, null, null)],
    ]);
    const links = [
        { predecessor_task_id: 1, successor_task_id: 2, lag_days: 0 },
        { predecessor_task_id: 1, successor_task_id: 3, lag_days: 2 },
        { predecessor_task_id: 1, successor_task_id: 4, lag_days: 0 },
        { predecessor_task_id: 9, successor_task_id: 2, lag_days: 0 },
    ];

    it("finds successors starting before the new due date plus lag", () => {
        expect(conflictingSuccessors(1, "2026-09-10", links, tasks)).toEqual([]);
        expect(conflictingSuccessors(1, "2026-09-11", links, tasks)).toEqual([2]);
        expect(conflictingSuccessors(1, "2026-09-19", links, tasks)).toEqual([2, 3]);
        expect(conflictingSuccessors(1, null, links, tasks)).toEqual([]);
    });
});

describe("isAlreadyLinked", () => {
    it("treats both directions as linked", () => {
        const links = [{ predecessor_task_id: 1, successor_task_id: 2, lag_days: 0 }];
        expect(isAlreadyLinked(1, 2, links)).toBe(true);
        expect(isAlreadyLinked(2, 1, links)).toBe(true);
        expect(isAlreadyLinked(1, 3, links)).toBe(false);
    });
});
