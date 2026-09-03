import type { TaskCompact, WbsNode } from "@/lib/types";

export interface WbsProgress {
    total: number;
    done: number;
    overdue: number;
}

export interface WbsTreeNode {
    node: WbsNode;
    /** Вычисленный номер ИСР: 1, 1.1, 1.2.1. В данных не хранится. */
    number: string;
    depth: number;
    children: WbsTreeNode[];
    /** Задачи, прикреплённые непосредственно к этому разделу. */
    tasks: TaskCompact[];
    /** Агрегат по всем задачам поддерева, включая вложенные разделы. */
    progress: WbsProgress;
}

export interface WbsTree {
    roots: WbsTreeNode[];
    byId: Map<number, WbsTreeNode>;
    /** Задачи вне структуры: и в списке-пуле, и выложенные на холст. */
    unassigned: TaskCompact[];
    /** Задачи, выложенные на холст, но ещё не связанные с разделом. */
    floating: TaskCompact[];
    total: WbsProgress;
}

/** Задача считается выложенной на холст, когда у неё есть обе координаты. */
export function isFloatingTask(task: TaskCompact): boolean {
    return task.wbs_node_id === null && task.canvas_x !== null && task.canvas_y !== null;
}

function emptyProgress(): WbsProgress {
    return { total: 0, done: 0, overdue: 0 };
}

function addProgress(target: WbsProgress, source: WbsProgress): void {
    target.total += source.total;
    target.done += source.done;
    target.overdue += source.overdue;
}

function taskProgress(tasks: TaskCompact[], isOverdue: (task: TaskCompact) => boolean): WbsProgress {
    return tasks.reduce<WbsProgress>((accumulator, task) => {
        accumulator.total += 1;
        if (task.is_done) {
            accumulator.done += 1;
        } else if (isOverdue(task)) {
            accumulator.overdue += 1;
        }
        return accumulator;
    }, emptyProgress());
}

/**
 * Собирает дерево ИСР из плоских списков.
 *
 * Номера считаются здесь, а не хранятся в БД: они выводятся из `parent_id`
 * и `position`, поэтому не могут разойтись со структурой после перемещения.
 * Прогресс раздела агрегирует задачи всех потомков.
 */
export function buildWbsTree(
    nodes: WbsNode[],
    tasks: TaskCompact[],
    isOverdue: (task: TaskCompact) => boolean = () => false,
): WbsTree {
    const childrenByParent = new Map<number | null, WbsNode[]>();
    for (const node of nodes) {
        const siblings = childrenByParent.get(node.parent_id) ?? [];
        siblings.push(node);
        childrenByParent.set(node.parent_id, siblings);
    }
    for (const siblings of childrenByParent.values()) {
        siblings.sort(
            (first, second) => first.position - second.position || first.id - second.id,
        );
    }

    const nodeIds = new Set(nodes.map((node) => node.id));
    const tasksByNode = new Map<number, TaskCompact[]>();
    const unassigned: TaskCompact[] = [];
    for (const task of tasks) {
        // Задача, чей раздел уже удалён, считается нераспределённой.
        if (task.wbs_node_id === null || !nodeIds.has(task.wbs_node_id)) {
            unassigned.push(task);
            continue;
        }
        const bucket = tasksByNode.get(task.wbs_node_id) ?? [];
        bucket.push(task);
        tasksByNode.set(task.wbs_node_id, bucket);
    }
    // Порядок задач внутри раздела задаёт пользователь перетаскиванием.
    for (const bucket of tasksByNode.values()) {
        bucket.sort(
            (first, second) =>
                (first.wbs_position ?? Number.MAX_SAFE_INTEGER) -
                    (second.wbs_position ?? Number.MAX_SAFE_INTEGER) || first.id - second.id,
        );
    }

    const byId = new Map<number, WbsTreeNode>();

    function build(node: WbsNode, prefix: string, index: number, depth: number): WbsTreeNode {
        const number = prefix === "" ? String(index + 1) : `${prefix}.${index + 1}`;
        const ownTasks = tasksByNode.get(node.id) ?? [];
        const progress = taskProgress(ownTasks, isOverdue);
        const children = (childrenByParent.get(node.id) ?? []).map((child, childIndex) =>
            build(child, number, childIndex, depth + 1),
        );
        for (const child of children) {
            addProgress(progress, child.progress);
        }

        const treeNode: WbsTreeNode = { node, number, depth, children, tasks: ownTasks, progress };
        byId.set(node.id, treeNode);
        return treeNode;
    }

    const roots = (childrenByParent.get(null) ?? []).map((node, index) =>
        build(node, "", index, 0),
    );

    const total = taskProgress(tasks, isOverdue);
    return { roots, byId, unassigned, floating: unassigned.filter(isFloatingTask), total };
}

/** Идентификаторы всех предков раздела — нужны, чтобы раскрыть путь к результату поиска. */
export function collectAncestorIds(nodes: WbsNode[], nodeId: number): number[] {
    const byId = new Map(nodes.map((node) => [node.id, node]));
    const ancestors: number[] = [];
    let current = byId.get(nodeId)?.parent_id ?? null;
    while (current !== null) {
        ancestors.push(current);
        current = byId.get(current)?.parent_id ?? null;
    }
    return ancestors;
}

/** Плоский список разделов в порядке обхода дерева — для выпадающих списков. */
export function flattenTree(roots: WbsTreeNode[]): WbsTreeNode[] {
    const result: WbsTreeNode[] = [];
    const walk = (nodes: WbsTreeNode[]) => {
        for (const node of nodes) {
            result.push(node);
            walk(node.children);
        }
    };
    walk(roots);
    return result;
}

/** Раздел нельзя перенести внутрь самого себя или собственного потомка. */
export function collectSubtreeIds(nodes: WbsNode[], rootId: number): Set<number> {
    const childrenByParent = new Map<number | null, WbsNode[]>();
    for (const node of nodes) {
        const siblings = childrenByParent.get(node.parent_id) ?? [];
        siblings.push(node);
        childrenByParent.set(node.parent_id, siblings);
    }

    const collected = new Set<number>([rootId]);
    const queue = [rootId];
    while (queue.length > 0) {
        const currentId = queue.pop() as number;
        for (const child of childrenByParent.get(currentId) ?? []) {
            if (!collected.has(child.id)) {
                collected.add(child.id);
                queue.push(child.id);
            }
        }
    }
    return collected;
}

export type SectionDropZone = "before" | "inside" | "after";

export interface SectionDropTarget {
    parentId: number | null;
    beforeId: number | null;
}

/**
 * Переводит зону сброса в параметры перемещения (§30 ТЗ).
 *
 * Backend принимает только «нового родителя» и «соседа, перед которым встать»,
 * поэтому позиция здесь не вычисляется — за неё отвечает сервер.
 */
export function resolveSectionDrop(
    nodes: WbsNode[],
    targetId: number,
    zone: SectionDropZone,
    movedId: number,
): SectionDropTarget | null {
    const target = nodes.find((node) => node.id === targetId);
    if (target === undefined || target.id === movedId) {
        return null;
    }
    if (zone === "inside") {
        return { parentId: target.id, beforeId: null };
    }

    const siblings = nodes
        .filter((node) => node.parent_id === target.parent_id && node.id !== movedId)
        .sort((first, second) => first.position - second.position || first.id - second.id);
    const index = siblings.findIndex((node) => node.id === target.id);
    if (index < 0) {
        return { parentId: target.parent_id, beforeId: null };
    }
    if (zone === "before") {
        return { parentId: target.parent_id, beforeId: target.id };
    }
    const next = siblings[index + 1];
    return { parentId: target.parent_id, beforeId: next?.id ?? null };
}
