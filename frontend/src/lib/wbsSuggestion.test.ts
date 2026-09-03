import { describe, expect, it } from "vitest";
import type { TaskCompact, WbsNode, WbsSuggestion } from "@/lib/types";
import {
    buildSuggestionPreview,
    flattenSuggestion,
    isDraftNodeId,
    removeSuggestedNode,
} from "@/lib/wbsSuggestion";

function node(id: number, parentId: number | null = null): WbsNode {
    return {
        id,
        project_id: 1,
        parent_id: parentId,
        title: `N${id}`,
        position: id * 1000,
        created_at: "2026-09-01T10:00:00Z",
        updated_at: "2026-09-01T10:00:00Z",
    };
}

function task(id: number, wbsNodeId: number | null = null): TaskCompact {
    return {
        id,
        key: `PROJ-${id}`,
        title: `Задача ${id}`,
        stage_id: 1,
        wbs_node_id: wbsNodeId,
        wbs_position: null,
        canvas_x: null,
        canvas_y: null,
        priority: "MEDIUM",
        assignee: null,
        start_date: null,
        due_date: null,
        is_done: false,
    };
}

const SUGGESTION: WbsSuggestion = {
    nodes: [
        { temp_id: "root", parent_temp_id: null, title: "Аналитика", rationale: null },
        { temp_id: "child", parent_temp_id: "root", title: "Интервью", rationale: null },
        { temp_id: "other", parent_temp_id: null, title: "Разработка", rationale: null },
    ],
    assignments: [
        { task_id: 11, node_temp_id: "child" },
        { task_id: 12, node_temp_id: "other" },
    ],
    summary: "",
    skipped_task_ids: [],
};

describe("buildSuggestionPreview", () => {
    it("добавляет предложенные разделы отрицательными идентификаторами", () => {
        const preview = buildSuggestionPreview(SUGGESTION, [node(5)], [task(11), task(12)], 1);

        const draftIds = preview.nodes.filter((item) => isDraftNodeId(item.id)).map((i) => i.id);
        expect(preview.nodes).toHaveLength(4);
        expect(draftIds).toEqual([-1, -2, -3]);
        // Настоящая структура остаётся нетронутой.
        expect(preview.nodes[0].id).toBe(5);
    });

    it("сохраняет вложенность черновика", () => {
        const preview = buildSuggestionPreview(SUGGESTION, [], [], 1);

        const child = preview.nodes.find((item) => item.title === "Интервью");
        const root = preview.nodes.find((item) => item.title === "Аналитика");
        expect(child?.parent_id).toBe(root?.id);
    });

    it("переносит задачи в предложенные разделы, но не в проекте", () => {
        const tasks = [task(11), task(12, 5), task(13)];

        const preview = buildSuggestionPreview(SUGGESTION, [node(5)], tasks, 1);

        expect(preview.tasks[0].wbs_node_id).toBe(-2);
        expect(preview.tasks[1].wbs_node_id).toBe(-3);
        // Задача вне предложения не меняется.
        expect(preview.tasks[2]).toBe(tasks[2]);
        expect(tasks[0].wbs_node_id).toBeNull();
    });

    it("нумерует задачи внутри предложенного раздела по порядку", () => {
        const suggestion: WbsSuggestion = {
            ...SUGGESTION,
            assignments: [
                { task_id: 11, node_temp_id: "root" },
                { task_id: 12, node_temp_id: "root" },
            ],
        };

        const preview = buildSuggestionPreview(suggestion, [], [task(11), task(12)], 1);

        expect(preview.tasks.map((item) => item.wbs_position)).toEqual([1000, 2000]);
    });
});

describe("removeSuggestedNode", () => {
    it("убирает раздел вместе с подразделами", () => {
        const result = removeSuggestedNode(SUGGESTION, "root");

        expect(result.nodes.map((item) => item.temp_id)).toEqual(["other"]);
    });

    it("возвращает задачи убранной ветки в число нетронутых", () => {
        const result = removeSuggestedNode(SUGGESTION, "root");

        expect(result.assignments.map((item) => item.task_id)).toEqual([12]);
        expect(result.skipped_task_ids).toEqual([11]);
    });
});

describe("flattenSuggestion", () => {
    it("разворачивает черновик от корней к листьям с уровнями", () => {
        expect(
            flattenSuggestion(SUGGESTION).map((item) => `${item.depth}:${item.node.temp_id}`),
        ).toEqual(["0:root", "1:child", "0:other"]);
    });
});
