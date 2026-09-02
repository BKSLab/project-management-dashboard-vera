import type { CalendarTask, CalendarWbsNode } from "@/lib/types";

export interface TimelineAggregate {
    total: number;
    done: number;
    risks: number;
    progress: number;
    startDate: string | null;
    dueDate: string | null;
}

export interface TimelineNodeRow {
    id: string;
    kind: "node" | "unassigned";
    depth: number;
    number: string | null;
    title: string;
    nodeId: number | null;
    collapsed: boolean;
    hasChildren: boolean;
    aggregate: TimelineAggregate;
}

export interface TimelineTaskRow {
    id: string;
    kind: "task";
    depth: number;
    task: CalendarTask;
}

export type TimelineWbsRow = TimelineNodeRow | TimelineTaskRow;

function aggregate(tasks: CalendarTask[]): TimelineAggregate {
    const scheduled = tasks.filter((task) => task.due_date !== null);
    const starts = scheduled.map((task) => task.start_date ?? (task.due_date as string));
    const ends = scheduled.map((task) => task.due_date as string);
    const done = tasks.filter((task) => task.is_done).length;
    return {
        total: tasks.length,
        done,
        risks: tasks.filter((task) => task.risk_level !== null && !task.is_done).length,
        progress: tasks.length === 0 ? 0 : Math.round((done / tasks.length) * 100),
        startDate: starts.length === 0 ? null : starts.sort()[0],
        dueDate: ends.length === 0 ? null : ends.sort().at(-1) ?? null,
    };
}

/** Строит синхронные строки ИСР и Timeline из плоского read model. */
export function buildTimelineWbsRows(
    nodes: CalendarWbsNode[],
    tasks: CalendarTask[],
    collapsedIds: ReadonlySet<number | "unassigned">,
): TimelineWbsRow[] {
    const nodeIds = new Set(nodes.map((node) => node.id));
    const children = new Map<number | null, CalendarWbsNode[]>();
    for (const node of nodes) {
        const parent = node.parent_id !== null && nodeIds.has(node.parent_id) ? node.parent_id : null;
        const bucket = children.get(parent) ?? [];
        bucket.push(node);
        children.set(parent, bucket);
    }
    for (const bucket of children.values()) {
        bucket.sort((first, second) => first.position - second.position || first.id - second.id);
    }

    const directTasks = new Map<number, CalendarTask[]>();
    const unassigned: CalendarTask[] = [];
    for (const task of tasks) {
        if (task.wbs_node_id === null || !nodeIds.has(task.wbs_node_id)) {
            unassigned.push(task);
        } else {
            const bucket = directTasks.get(task.wbs_node_id) ?? [];
            bucket.push(task);
            directTasks.set(task.wbs_node_id, bucket);
        }
    }
    const sortTasks = (items: CalendarTask[]) =>
        items.sort(
            (first, second) =>
                (first.start_date ?? first.due_date ?? "").localeCompare(
                    second.start_date ?? second.due_date ?? "",
                ) || first.key.localeCompare(second.key),
        );
    sortTasks(unassigned);
    for (const bucket of directTasks.values()) sortTasks(bucket);

    const subtreeTasks = new Map<number, CalendarTask[]>();
    const collect = (nodeId: number, visiting = new Set<number>()): CalendarTask[] => {
        if (visiting.has(nodeId)) return [];
        const cached = subtreeTasks.get(nodeId);
        if (cached) return cached;
        const nextVisiting = new Set(visiting).add(nodeId);
        const result = [...(directTasks.get(nodeId) ?? [])];
        for (const child of children.get(nodeId) ?? []) {
            result.push(...collect(child.id, nextVisiting));
        }
        subtreeTasks.set(nodeId, result);
        return result;
    };

    const rows: TimelineWbsRow[] = [];
    const walk = (node: CalendarWbsNode, number: string, depth: number) => {
        const nested = children.get(node.id) ?? [];
        const ownTasks = directTasks.get(node.id) ?? [];
        const collapsed = collapsedIds.has(node.id);
        rows.push({
            id: `node:${node.id}`,
            kind: "node",
            depth,
            number,
            title: node.title,
            nodeId: node.id,
            collapsed,
            hasChildren: nested.length > 0 || ownTasks.length > 0,
            aggregate: aggregate(collect(node.id)),
        });
        if (collapsed) return;
        for (const task of ownTasks) {
            rows.push({ id: `task:${task.id}`, kind: "task", depth: depth + 1, task });
        }
        nested.forEach((child, index) => walk(child, `${number}.${index + 1}`, depth + 1));
    };
    (children.get(null) ?? []).forEach((node, index) => walk(node, String(index + 1), 0));

    if (unassigned.length > 0) {
        const collapsed = collapsedIds.has("unassigned");
        rows.push({
            id: "node:unassigned",
            kind: "unassigned",
            depth: 0,
            number: null,
            title: "Без раздела ИСР",
            nodeId: null,
            collapsed,
            hasChildren: true,
            aggregate: aggregate(unassigned),
        });
        if (!collapsed) {
            for (const task of unassigned) {
                rows.push({ id: `task:${task.id}`, kind: "task", depth: 1, task });
            }
        }
    }
    return rows;
}
