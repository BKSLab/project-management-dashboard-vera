import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";
import type { TaskCompact, TaskDependency } from "@/lib/types";
import type { WbsTreeNode } from "@/lib/wbsTree";

export type WbsLayoutMode = "vertical" | "horizontal";

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
    /**
     * Задача лежит на холсте вне структуры. Её координаты задал пользователь,
     * поэтому раскладка их не трогает.
     */
    fixedPosition?: { x: number; y: number };
}

export interface WbsGraphEdge {
    id: string;
    source: string;
    target: string;
    /**
     * Связь разделов держит раскладку, привязку задачи рисует пользователь,
     * зависимость — это последовательность работ и на раскладку не влияет.
     */
    kind: "structure" | "attachment" | "dependency";
    /** Идентификатор зависимости в БД: по нему связь и удаляют. */
    dependencyId?: number;
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
// Высота считается по содержимому карточки: ключ с бейджем, заголовок и
// строка стадии со сроком. Если её занизить, заголовок схлопывается в ноль.
export const TASK_NODE_SIZE = { width: 232, height: 78 };

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
):
    | { kind: "project" }
    | { kind: "section"; nodeId: number }
    | { kind: "task"; taskId: number }
    | null {
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
    /** Задачи, выложенные на холст вне структуры. */
    floatingTasks: TaskCompact[];
    /** Зависимости задач проекта: показываем те, чьи концы видны на холсте. */
    dependencies: TaskDependency[];
}

/**
 * Строит граф из дерева ИСР.
 *
 * Рёбра появляются только из `parent_id` и `wbs_node_id`: стрелку от раздела
 * к задаче пользователь рисует, но она означает ровно привязку задачи, а не
 * самостоятельную связь.
 */
export function buildWbsGraph({
    roots,
    collapsed,
    showTasks,
    floatingTasks,
    dependencies,
}: BuildGraphOptions): WbsGraph {
    const nodes: WbsGraphNode[] = [{ id: PROJECT_NODE_ID, kind: "project", ...PROJECT_NODE_SIZE }];
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
        edges.push({
            id: `${parentGraphId}->${graphId}`,
            source: parentGraphId,
            target: graphId,
            kind: "structure",
        });

        if (isCollapsed) {
            return;
        }

        if (showTasks) {
            for (const task of section.tasks) {
                const taskGraphId = taskNodeId(task.id);
                nodes.push({ id: taskGraphId, kind: "task", task, ...TASK_NODE_SIZE });
                edges.push({
                    id: `${graphId}->${taskGraphId}`,
                    source: graphId,
                    target: taskGraphId,
                    kind: "attachment",
                });
            }
        }

        for (const child of section.children) {
            walk(child, graphId);
        }
    }

    for (const root of roots) {
        walk(root, PROJECT_NODE_ID);
    }

    // Карточки на холсте живут вне структуры: ни рёбер, ни расчёта позиции.
    for (const task of floatingTasks) {
        nodes.push({
            id: taskNodeId(task.id),
            kind: "task",
            task,
            fixedPosition: { x: task.canvas_x ?? 0, y: task.canvas_y ?? 0 },
            ...TASK_NODE_SIZE,
        });
    }

    // Зависимость рисуется, только когда обе задачи видны: иначе стрелка
    // повисает в пустоте и вводит в заблуждение.
    const visibleTaskIds = new Set(
        nodes.filter((node) => node.kind === "task").map((node) => node.task?.id),
    );
    for (const dependency of dependencies) {
        if (
            !visibleTaskIds.has(dependency.predecessor_task_id) ||
            !visibleTaskIds.has(dependency.successor_task_id)
        ) {
            continue;
        }
        edges.push({
            id: `dependency-${dependency.id}`,
            source: taskNodeId(dependency.predecessor_task_id),
            target: taskNodeId(dependency.successor_task_id),
            kind: "dependency",
            dependencyId: dependency.id,
        });
    }

    return { nodes, edges };
}

const elk = new ELK();

const LAYOUT_OPTIONS: Record<WbsLayoutMode, Record<string, string>> = {
    vertical: {
        "elk.algorithm": "layered",
        "elk.direction": "DOWN",
        "elk.layered.spacing.nodeNodeBetweenLayers": "48",
        "elk.spacing.nodeNode": "28",
        "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
        "elk.layered.crossingMinimization.semiInteractive": "true",
        // Порядок задач внутри раздела задаёт пользователь — раскладка
        // не должна переставлять их ради красоты рёбер.
        "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    },
    horizontal: {
        "elk.algorithm": "layered",
        "elk.direction": "RIGHT",
        "elk.layered.spacing.nodeNodeBetweenLayers": "72",
        "elk.spacing.nodeNode": "24",
        "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
        "elk.layered.crossingMinimization.semiInteractive": "true",
        // Порядок задач внутри раздела задаёт пользователь — раскладка
        // не должна переставлять их ради красоты рёбер.
        "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    },
};

/**
 * Считает координаты блок-схемы.
 *
 * Задачи участвуют в раскладке наравне с разделами: в ИСР работы одного
 * раздела — параллельные ветки, поэтому они встают в ряд под своим разделом,
 * а не выстраиваются друг за другом. Порядок внутри ряда — тот, который задал
 * пользователь. Карточки на холсте раскладке не подчиняются: их координаты он
 * задал сам.
 */
export async function layoutWbsGraph(
    graph: WbsGraph,
    mode: WbsLayoutMode,
): Promise<WbsLayoutResult> {
    const laidOut = graph.nodes.filter((node) => node.fixedPosition === undefined);
    const present = new Set(laidOut.map((node) => node.id));
    const elkGraph: ElkNode = {
        id: "root",
        layoutOptions: LAYOUT_OPTIONS[mode],
        children: laidOut.map((node) => ({
            id: node.id,
            width: node.width,
            height: node.height,
        })),
        edges: graph.edges
            // Последовательность работ не должна перестраивать саму структуру.
            .filter((edge) => edge.kind !== "dependency")
            .filter((edge) => present.has(edge.source) && present.has(edge.target))
            .map((edge) => ({ id: edge.id, sources: [edge.source], targets: [edge.target] })),
    };

    const layout = await elk.layout(elkGraph);
    const positions = new Map<string, { x: number; y: number }>();
    for (const child of layout.children ?? []) {
        positions.set(child.id, { x: child.x ?? 0, y: child.y ?? 0 });
    }
    for (const node of graph.nodes) {
        if (node.fixedPosition !== undefined) {
            positions.set(node.id, node.fixedPosition);
        }
    }
    return { positions };
}
