import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";
import type { TaskCompact } from "@/lib/types";
import type { WbsTreeNode } from "@/lib/wbsTree";

export type WbsLayoutMode = "horizontal" | "vertical";

export interface WbsGraphNode {
    id: string;
    kind: "project" | "section" | "task";
    width: number;
    height: number;
    section?: WbsTreeNode;
    task?: TaskCompact;
    /** Свёрнутый раздел показывает агрегат вместо потомков. */
    isCollapsed?: boolean;
    hiddenSections?: number;
    hiddenTasks?: number;
}

export interface WbsGraphEdge {
    id: string;
    source: string;
    target: string;
}

export interface WbsGraph {
    nodes: WbsGraphNode[];
    edges: WbsGraphEdge[];
}

export interface WbsLayoutResult {
    positions: Map<string, { x: number; y: number }>;
}

export const PROJECT_NODE_SIZE = { width: 240, height: 96 };
export const SECTION_NODE_SIZE = { width: 220, height: 86 };
export const NESTED_SECTION_NODE_SIZE = { width: 200, height: 78 };
export const TASK_NODE_SIZE = { width: 232, height: 62 };

export const PROJECT_NODE_ID = "project-root";

export function sectionNodeId(nodeId: number): string {
    return `section-${nodeId}`;
}

export function taskNodeId(taskId: number): string {
    return `task-${taskId}`;
}

/** Разбирает идентификатор узла графа обратно в доменную ссылку. */
export function parseGraphNodeId(
    id: string,
): { kind: "project" } | { kind: "section"; nodeId: number } | { kind: "task"; taskId: number } | null {
    if (id === PROJECT_NODE_ID) {
        return { kind: "project" };
    }
    if (id.startsWith("section-")) {
        return { kind: "section", nodeId: Number(id.slice("section-".length)) };
    }
    if (id.startsWith("task-")) {
        return { kind: "task", taskId: Number(id.slice("task-".length)) };
    }
    return null;
}

interface BuildGraphOptions {
    roots: WbsTreeNode[];
    collapsed: Set<number>;
    /** При сильном отдалении отдельные задачи скрываются (semantic zoom, §34). */
    showTasks: boolean;
}

/**
 * Строит граф из дерева ИСР. Рёбра появляются только из `parent_id` и
 * `wbs_node_id` — пользователь не рисует связи вручную (§23 ТЗ).
 */
export function buildWbsGraph({ roots, collapsed, showTasks }: BuildGraphOptions): WbsGraph {
    const nodes: WbsGraphNode[] = [
        { id: PROJECT_NODE_ID, kind: "project", ...PROJECT_NODE_SIZE },
    ];
    const edges: WbsGraphEdge[] = [];

    function countHidden(section: WbsTreeNode): { sections: number; tasks: number } {
        let sections = 0;
        let tasks = section.tasks.length;
        for (const child of section.children) {
            const nested = countHidden(child);
            sections += 1 + nested.sections;
            tasks += nested.tasks;
        }
        return { sections, tasks };
    }

    function walk(section: WbsTreeNode, parentGraphId: string): void {
        const graphId = sectionNodeId(section.node.id);
        const isCollapsed = collapsed.has(section.node.id);
        const hidden = isCollapsed ? countHidden(section) : { sections: 0, tasks: 0 };
        const size = section.depth === 0 ? SECTION_NODE_SIZE : NESTED_SECTION_NODE_SIZE;

        nodes.push({
            id: graphId,
            kind: "section",
            section,
            isCollapsed,
            hiddenSections: hidden.sections,
            hiddenTasks: hidden.tasks,
            ...size,
        });
        edges.push({ id: `${parentGraphId}->${graphId}`, source: parentGraphId, target: graphId });

        if (isCollapsed) {
            return;
        }

        for (const child of section.children) {
            walk(child, graphId);
        }

        if (!showTasks) {
            return;
        }
        for (const task of section.tasks) {
            const taskGraphId = taskNodeId(task.id);
            nodes.push({ id: taskGraphId, kind: "task", task, ...TASK_NODE_SIZE });
            edges.push({
                id: `${graphId}->${taskGraphId}`,
                source: graphId,
                target: taskGraphId,
            });
        }
    }

    for (const root of roots) {
        walk(root, PROJECT_NODE_ID);
    }

    return { nodes, edges };
}

const elk = new ELK();

const LAYOUT_OPTIONS: Record<WbsLayoutMode, Record<string, string>> = {
    horizontal: {
        "elk.algorithm": "layered",
        "elk.direction": "RIGHT",
        "elk.layered.spacing.nodeNodeBetweenLayers": "72",
        "elk.spacing.nodeNode": "18",
        "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
        "elk.layered.crossingMinimization.semiInteractive": "true",
    },
    vertical: {
        "elk.algorithm": "layered",
        "elk.direction": "DOWN",
        "elk.layered.spacing.nodeNodeBetweenLayers": "56",
        "elk.spacing.nodeNode": "24",
        "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
        "elk.layered.crossingMinimization.semiInteractive": "true",
    },
};

/**
 * Считает координаты узлов. Позиции — производное состояние интерфейса:
 * пользователь не расставляет блоки вручную (§17 ТЗ).
 */
export async function layoutWbsGraph(
    graph: WbsGraph,
    mode: WbsLayoutMode,
): Promise<WbsLayoutResult> {
    const elkGraph: ElkNode = {
        id: "root",
        layoutOptions: LAYOUT_OPTIONS[mode],
        children: graph.nodes.map((node) => ({
            id: node.id,
            width: node.width,
            height: node.height,
        })),
        edges: graph.edges.map((edge) => ({
            id: edge.id,
            sources: [edge.source],
            targets: [edge.target],
        })),
    };

    const layout = await elk.layout(elkGraph);
    const positions = new Map<string, { x: number; y: number }>();
    for (const child of layout.children ?? []) {
        positions.set(child.id, { x: child.x ?? 0, y: child.y ?? 0 });
    }
    return { positions };
}
