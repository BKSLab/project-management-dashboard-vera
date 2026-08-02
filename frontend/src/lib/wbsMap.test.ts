import { describe, expect, it } from "vitest";
import type { KanbanStage, WbsNode } from "@/lib/types";
import { buildWbsMapModel, stageCount } from "@/lib/wbsMap";

const stages: KanbanStage[] = [
    { id: 1, name: "Бэклог", order_index: 0, color: "#999999", is_done_stage: false },
    { id: 2, name: "В работе", order_index: 1, color: "#F5B800", is_done_stage: false },
    { id: 3, name: "Готово", order_index: 2, color: "#22C55E", is_done_stage: true },
];

function leaf(
    id: number,
    code: string,
    title: string,
    stageId: number,
    dueDate: string | null = null,
): WbsNode {
    const stage = stages.find((item) => item.id === stageId)!;
    return {
        id,
        code,
        phase_name: null,
        title,
        role: null,
        progress: null,
        task: { id: id * 10, stage_id: stageId, stage_name: stage.name, due_date: dueDate },
        children: [],
    };
}

const tree: WbsNode[] = [
    {
        id: 1,
        code: "1",
        phase_name: "Разработка",
        title: "Разработка",
        role: null,
        progress: { done: 1, total: 2 },
        task: null,
        children: [
            {
                id: 2,
                code: "1.1",
                phase_name: null,
                title: "Backend",
                role: "BE",
                progress: { done: 1, total: 2 },
                task: null,
                children: [
                    leaf(3, "1.1.1", "Готовая задача", 3),
                    leaf(4, "1.1.2", "Просроченная задача", 2, "2026-08-01"),
                ],
            },
        ],
    },
    {
        id: 5,
        code: "2",
        phase_name: "Запуск",
        title: "Запуск",
        role: null,
        progress: { done: 0, total: 1 },
        task: null,
        children: [leaf(6, "2.1", "Задача в бэклоге", 1)],
    },
];

describe("buildWbsMapModel", () => {
    it("считает стадии, выполнение и просрочки по всему дереву", () => {
        const model = buildWbsMapModel(tree, stages, {
            expandedNodeIds: new Set([1, 5]),
            activeRootId: null,
            search: "",
            now: new Date("2026-08-02T12:00:00Z"),
        });

        expect(model.summary).toMatchObject({ taskCount: 3, doneCount: 1, overdueCount: 1 });
        expect(stageCount(model.summary, 1)).toBe(1);
        expect(stageCount(model.summary, 2)).toBe(1);
        expect(stageCount(model.summary, 3)).toBe(1);
        expect(model.totalNodeCount).toBe(6);
        expect(model.visibleNodeCount).toBe(4);
    });

    it("раскладывает раскрытое дерево сверху вниз и соединяет каждый дочерний узел", () => {
        const model = buildWbsMapModel(tree, stages, {
            expandedNodeIds: new Set([1, 2, 5]),
            activeRootId: null,
            search: "",
            now: new Date("2026-08-02T12:00:00Z"),
        });
        const project = model.nodes.find((node) => node.key === "project-root")!;
        const phase = model.nodes.find((node) => node.sourceId === 1)!;
        const task = model.nodes.find((node) => node.sourceId === 3)!;

        expect(model.visibleNodeCount).toBe(6);
        expect(model.edges).toHaveLength(6);
        expect(project.y).toBeLessThan(phase.y);
        expect(phase.y).toBeLessThan(task.y);
        expect(model.width).toBeGreaterThan(640);
        expect(model.height).toBeGreaterThan(420);
    });

    it("автоматически раскрывает путь к найденной задаче", () => {
        const model = buildWbsMapModel(tree, stages, {
            expandedNodeIds: new Set(),
            activeRootId: null,
            search: "готовая",
            now: new Date("2026-08-02T12:00:00Z"),
        });

        expect(model.searchResults).toEqual([
            { nodeId: 3, code: "1.1.1", title: "Готовая задача", taskId: 30 },
        ]);
        expect(model.nodes.some((node) => node.sourceId === 3 && node.directSearchMatch)).toBe(true);
        expect(model.nodes.find((node) => node.sourceId === 1)?.containsSearchMatch).toBe(true);
    });

    it("ограничивает карту и результаты поиска выбранной фазой", () => {
        const model = buildWbsMapModel(tree, stages, {
            expandedNodeIds: new Set([5]),
            activeRootId: 5,
            search: "готовая",
            now: new Date("2026-08-02T12:00:00Z"),
        });

        expect(model.totalNodeCount).toBe(2);
        expect(model.summary.taskCount).toBe(1);
        expect(model.searchResults).toHaveLength(0);
        expect(model.nodes.some((node) => node.sourceId === 1)).toBe(false);
    });
});
