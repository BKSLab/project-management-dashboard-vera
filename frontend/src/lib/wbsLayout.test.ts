import { describe, expect, it } from "vitest";
import type { TaskCompact, WbsNode } from "@/lib/types";
import {
    buildWbsGraph,
    layoutWbsGraph,
    parseGraphNodeId,
    PROJECT_NODE_ID,
} from "@/lib/wbsLayout";
import { buildWbsTree } from "@/lib/wbsTree";

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

function task(
    id: number,
    wbsNodeId: number | null,
    wbsPosition: number | null = null,
    canvas: { x: number; y: number } | null = null,
): TaskCompact {
    return {
        id,
        key: `PROJ-${id}`,
        title: `Задача ${id}`,
        stage_id: 1,
        wbs_node_id: wbsNodeId,
        wbs_position: wbsPosition,
        canvas_x: canvas?.x ?? null,
        canvas_y: canvas?.y ?? null,
        priority: "MEDIUM",
        assignee: null,
        start_date: null,
        due_date: null,
        is_done: false,
    };
}

function buildGraph(nodes: WbsNode[], tasks: TaskCompact[], showTasks = true) {
    const tree = buildWbsTree(nodes, tasks);
    return buildWbsGraph({
        roots: tree.roots,
        collapsed: new Set<number>(),
        showTasks,
        floatingTasks: tree.floating,
    });
}

describe("layoutWbsGraph", () => {
    it("ставит задачи раздела в один ряд под ним, а не друг за другом", async () => {
        const graph = buildGraph(
            [node(1)],
            [task(11, 1, 1000), task(12, 1, 2000), task(13, 1, 3000)],
        );

        const { positions } = await layoutWbsGraph(graph, "vertical");
        const section = positions.get("section-1");
        const tasks = ["task-11", "task-12", "task-13"].map(
            (id) => positions.get(id) as { x: number; y: number },
        );

        expect(section).toBeDefined();
        // Один ряд: общая координата по вертикали и разные — по горизонтали.
        expect(new Set(tasks.map((item) => item.y)).size).toBe(1);
        expect(new Set(tasks.map((item) => item.x)).size).toBe(3);
        expect(tasks.every((item) => item.y > (section as { y: number }).y)).toBe(true);
        // Порядок ряда повторяет порядок, заданный пользователем.
        expect([...tasks].sort((first, second) => first.x - second.x)).toEqual(tasks);
    });

    it("оставляет карточку холста там, куда её положил пользователь", async () => {
        const graph = buildGraph([node(1)], [task(11, null, null, { x: 420, y: 180 })]);

        const { positions } = await layoutWbsGraph(graph, "vertical");

        expect(positions.get("task-11")).toEqual({ x: 420, y: 180 });
    });
});

describe("buildWbsGraph", () => {
    it("выстраивает задачи раздела в порядке, заданном пользователем", () => {
        const graph = buildGraph([node(1)], [task(11, 1, 2000), task(12, 1, 1000)]);

        const tasks = graph.nodes.filter((item) => item.kind === "task");
        expect(tasks.map((item) => item.task?.id)).toEqual([12, 11]);
    });

    it("отличает связь разделов от привязки задачи", () => {
        const graph = buildGraph([node(1), node(2, 1)], [task(11, 2)]);

        const kinds = new Map(graph.edges.map((edge) => [edge.id, edge.kind]));
        expect(kinds.get(`${PROJECT_NODE_ID}->section-1`)).toBe("structure");
        expect(kinds.get("section-1->section-2")).toBe("structure");
        expect(kinds.get("section-2->task-11")).toBe("attachment");
    });

    it("кладёт карточку на холст в заданную точку и без связей", () => {
        const graph = buildGraph([node(1)], [task(11, null, null, { x: 420, y: 180 })]);

        const floating = graph.nodes.find(
            (item) => parseGraphNodeId(item.id)?.kind === "task",
        );
        expect(floating?.fixedPosition).toEqual({ x: 420, y: 180 });
        expect(graph.edges.some((edge) => edge.target === "task-11")).toBe(false);
    });

    it("не показывает задачи при сильном отдалении, кроме лежащих на холсте", () => {
        const graph = buildGraph(
            [node(1)],
            [task(11, 1, 1000), task(12, null, null, { x: 0, y: 0 })],
            false,
        );

        expect(graph.nodes.filter((item) => item.kind === "task").map((item) => item.id)).toEqual([
            "task-12",
        ]);
    });
});
