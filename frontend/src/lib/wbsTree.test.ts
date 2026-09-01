import { describe, expect, it } from "vitest";
import type { TaskCompact, WbsNode } from "@/lib/types";
import {
    buildWbsTree,
    collectAncestorIds,
    collectSubtreeIds,
    flattenTree,
    resolveSectionDrop,
} from "@/lib/wbsTree";

function node(id: number, parentId: number | null, position: number, title = `N${id}`): WbsNode {
    return {
        id,
        project_id: 1,
        parent_id: parentId,
        title,
        position,
        created_at: "2026-09-01T10:00:00Z",
        updated_at: "2026-09-01T10:00:00Z",
    };
}

function task(
    id: number,
    wbsNodeId: number | null,
    isDone = false,
    dueDate: string | null = null,
): TaskCompact {
    return {
        id,
        key: `VERA-${id}`,
        title: `Задача ${id}`,
        stage_id: 1,
        wbs_node_id: wbsNodeId,
        priority: "MEDIUM",
        assignee: null,
        due_date: dueDate,
        is_done: isDone,
    };
}

const OVERDUE = (item: TaskCompact) => item.due_date === "past";

describe("buildWbsTree", () => {
    it("нумерует разделы по позиции, а не по идентификатору", () => {
        const nodes = [
            node(3, null, 3000, "Deployment"),
            node(1, null, 1000, "Backend"),
            node(2, null, 2000, "Frontend"),
            node(5, 1, 2000, "Database"),
            node(4, 1, 1000, "API"),
        ];

        const tree = buildWbsTree(nodes, []);

        expect(tree.roots.map((item) => `${item.number} ${item.node.title}`)).toEqual([
            "1 Backend",
            "2 Frontend",
            "3 Deployment",
        ]);
        expect(tree.roots[0].children.map((item) => `${item.number} ${item.node.title}`)).toEqual([
            "1.1 API",
            "1.2 Database",
        ]);
    });

    it("перенумеровывает ветку после смены позиций", () => {
        const moved = [node(1, null, 1000), node(5, 1, 500, "Database"), node(4, 1, 1000, "API")];

        const tree = buildWbsTree(moved, []);

        expect(tree.roots[0].children.map((item) => item.number)).toEqual(["1.1", "1.2"]);
        expect(tree.roots[0].children[0].node.title).toBe("Database");
    });

    it("агрегирует прогресс по всем потомкам", () => {
        const nodes = [node(1, null, 1000), node(2, 1, 1000), node(3, 2, 1000)];
        const tasks = [
            task(11, 1, true),
            task(12, 2, false),
            task(13, 3, true),
            task(14, 3, false, "past"),
        ];

        const tree = buildWbsTree(nodes, tasks, OVERDUE);
        const root = tree.roots[0];

        expect(root.progress).toEqual({ total: 4, done: 2, overdue: 1 });
        expect(root.children[0].progress).toEqual({ total: 3, done: 1, overdue: 1 });
        expect(root.tasks.map((item) => item.id)).toEqual([11]);
    });

    it("считает задачу без раздела нераспределённой", () => {
        const tree = buildWbsTree([node(1, null, 1000)], [task(11, null), task(12, 1)]);

        expect(tree.unassigned.map((item) => item.id)).toEqual([11]);
    });

    it("возвращает в пул задачу удалённого раздела", () => {
        const tree = buildWbsTree([node(1, null, 1000)], [task(11, 99)]);

        expect(tree.unassigned.map((item) => item.id)).toEqual([11]);
        expect(tree.roots[0].progress.total).toBe(0);
    });

    it("считает общий прогресс по всем задачам проекта", () => {
        const tree = buildWbsTree(
            [node(1, null, 1000)],
            [task(11, 1, true), task(12, null, false, "past")],
            OVERDUE,
        );

        expect(tree.total).toEqual({ total: 2, done: 1, overdue: 1 });
    });
});

describe("collectSubtreeIds", () => {
    it("собирает узел и всех его потомков", () => {
        const nodes = [node(1, null, 1000), node(2, 1, 1000), node(3, 2, 1000), node(4, null, 2000)];

        expect(collectSubtreeIds(nodes, 1)).toEqual(new Set([1, 2, 3]));
        expect(collectSubtreeIds(nodes, 4)).toEqual(new Set([4]));
    });
});

describe("collectAncestorIds", () => {
    it("возвращает путь до корня", () => {
        const nodes = [node(1, null, 1000), node(2, 1, 1000), node(3, 2, 1000)];

        expect(collectAncestorIds(nodes, 3)).toEqual([2, 1]);
        expect(collectAncestorIds(nodes, 1)).toEqual([]);
    });
});

describe("flattenTree", () => {
    it("разворачивает дерево в порядке обхода", () => {
        const nodes = [node(1, null, 1000), node(2, 1, 1000), node(3, null, 2000)];

        const flat = flattenTree(buildWbsTree(nodes, []).roots);

        expect(flat.map((item) => item.number)).toEqual(["1", "1.1", "2"]);
    });
});

describe("resolveSectionDrop", () => {
    const nodes = [
        node(1, null, 1000, "Backend"),
        node(2, null, 2000, "Frontend"),
        node(3, null, 3000, "Deployment"),
        node(4, 1, 1000, "API"),
    ];

    it("делает раздел дочерним при сбросе внутрь", () => {
        expect(resolveSectionDrop(nodes, 2, "inside", 3)).toEqual({ parentId: 2, beforeId: null });
    });

    it("ставит раздел перед целевым на том же уровне", () => {
        expect(resolveSectionDrop(nodes, 2, "before", 3)).toEqual({ parentId: null, beforeId: 2 });
    });

    it("ставит раздел после целевого, то есть перед следующим соседом", () => {
        expect(resolveSectionDrop(nodes, 1, "after", 3)).toEqual({ parentId: null, beforeId: 2 });
    });

    it("после последнего соседа отправляет раздел в конец уровня", () => {
        expect(resolveSectionDrop(nodes, 3, "after", 1)).toEqual({ parentId: null, beforeId: null });
    });

    it("не даёт сбросить раздел на самого себя", () => {
        expect(resolveSectionDrop(nodes, 1, "inside", 1)).toBeNull();
    });
});
