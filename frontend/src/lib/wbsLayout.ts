import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";
import type { TaskCompact } from "@/lib/types";
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
    /** Раздел-владелец задачи: под ним задача и встаёт стопкой. */
    parentId?: string;
    /** Порядковый номер задачи в стопке своего раздела. */
    stackIndex?: number;
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
    /** Связь разделов держит раскладка, привязку задачи рисует пользователь. */
    kind: "structure" | "attachment";
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

/** Отступ стопки задач от левого края раздела — место для вертикальной связки. */
const TASK_STACK_INDENT = 26;
const TASK_STACK_GAP = 8;
/** Зазор между низом раздела и первой задачей его стопки. */
const SECTION_TASK_GAP = 14;

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
            section.tasks.forEach((task, index) => {
                const taskGraphId = taskNodeId(task.id);
                nodes.push({
                    id: taskGraphId,
                    kind: "task",
                    task,
                    parentId: graphId,
                    stackIndex: index,
                    ...TASK_NODE_SIZE,
                });
                edges.push({
                    id: `${graphId}->${taskGraphId}`,
                    source: graphId,
                    target: taskGraphId,
                    kind: "attachment",
                });
            });
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
    },
    horizontal: {
        "elk.algorithm": "layered",
        "elk.direction": "RIGHT",
        "elk.layered.spacing.nodeNodeBetweenLayers": "72",
        "elk.spacing.nodeNode": "24",
        "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
        "elk.layered.crossingMinimization.semiInteractive": "true",
    },
};

/**
 * Считает координаты блок-схемы.
 *
 * Раскладку получают только разделы: задачи встают стопкой под своим
 * разделом, поэтому ветка читается как блок-схема, а не расползается вширь.
 * Раздел резервирует место под собственную стопку, чтобы соседние ветки на
 * неё не наехали. Карточки на холсте раскладке не подчиняются: их координаты
 * задал пользователь.
 */
export async function layoutWbsGraph(
    graph: WbsGraph,
    mode: WbsLayoutMode,
): Promise<WbsLayoutResult> {
    const stacks = new Map<string, WbsGraphNode[]>();
    for (const node of graph.nodes) {
        if (node.kind !== "task" || node.parentId === undefined) {
            continue;
        }
        const stack = stacks.get(node.parentId) ?? [];
        stack.push(node);
        stacks.set(node.parentId, stack);
    }

    const laidOut = graph.nodes.filter(
        (node) => node.kind !== "task" && node.fixedPosition === undefined,
    );
    const elkGraph: ElkNode = {
        id: "root",
        layoutOptions: LAYOUT_OPTIONS[mode],
        children: laidOut.map((node) => ({
            id: node.id,
            width: Math.max(node.width, stackWidth(stacks.get(node.id))),
            height: node.height + stackHeight(stacks.get(node.id)),
        })),
        edges: graph.edges
            .filter((edge) => edge.kind === "structure")
            .map((edge) => ({ id: edge.id, sources: [edge.source], targets: [edge.target] })),
    };

    const layout = await elk.layout(elkGraph);
    const positions = new Map<string, { x: number; y: number }>();
    for (const child of layout.children ?? []) {
        positions.set(child.id, { x: child.x ?? 0, y: child.y ?? 0 });
    }

    for (const [sectionId, stack] of stacks) {
        const anchor = positions.get(sectionId);
        const section = laidOut.find((node) => node.id === sectionId);
        if (anchor === undefined || section === undefined) {
            continue;
        }
        const top = anchor.y + section.height + SECTION_TASK_GAP;
        stack.forEach((node, index) => {
            positions.set(node.id, {
                x: anchor.x + TASK_STACK_INDENT,
                y: top + index * (node.height + TASK_STACK_GAP),
            });
        });
    }

    for (const node of graph.nodes) {
        if (node.fixedPosition !== undefined) {
            positions.set(node.id, node.fixedPosition);
        }
    }
    return { positions };
}

/** Место, которое стопка задач занимает по вертикали вместе с зазорами. */
function stackHeight(stack: WbsGraphNode[] | undefined): number {
    if (stack === undefined || stack.length === 0) {
        return 0;
    }
    return (
        SECTION_TASK_GAP +
        stack.reduce((total, node) => total + node.height + TASK_STACK_GAP, 0) -
        TASK_STACK_GAP
    );
}

/** Ширина, которую резервирует стопка задач с учётом отступа связки. */
function stackWidth(stack: WbsGraphNode[] | undefined): number {
    if (stack === undefined || stack.length === 0) {
        return 0;
    }
    return TASK_STACK_INDENT + Math.max(...stack.map((node) => node.width));
}
