import type { TaskCompact, WbsNode, WbsSuggestedNode, WbsSuggestion } from "@/lib/types";

/** Шаг позиции черновика: он же шаг разреженных позиций на backend. */
const DRAFT_POSITION_STEP = 1000;

/**
 * Разделы черновика живут в общих списках с отрицательными идентификаторами:
 * по знаку холст и отличает предложение от сохранённой структуры.
 */
export function isDraftNodeId(nodeId: number): boolean {
    return nodeId < 0;
}

/** Разворачивает черновик в плоский список с уровнем вложенности. */
export function flattenSuggestion(
    suggestion: WbsSuggestion,
): { node: WbsSuggestedNode; depth: number }[] {
    const childrenByParent = new Map<string | null, WbsSuggestedNode[]>();
    for (const node of suggestion.nodes) {
        const siblings = childrenByParent.get(node.parent_temp_id) ?? [];
        siblings.push(node);
        childrenByParent.set(node.parent_temp_id, siblings);
    }

    const result: { node: WbsSuggestedNode; depth: number }[] = [];
    const walk = (parent: string | null, depth: number) => {
        for (const node of childrenByParent.get(parent) ?? []) {
            result.push({ node, depth });
            walk(node.temp_id, depth + 1);
        }
    };
    walk(null, 0);
    return result;
}

export interface SuggestionPreview {
    nodes: WbsNode[];
    tasks: TaskCompact[];
}

/**
 * Собирает предпросмотр черновика поверх настоящей структуры.
 *
 * Предложенные разделы получают отрицательные идентификаторы: так они
 * проходят через те же дерево, раскладку и canvas, что и сохранённые, но
 * остаются отличимыми — по знаку идентификатора холст рисует их пунктиром и
 * запрещает перетаскивание.
 */
export function buildSuggestionPreview(
    suggestion: WbsSuggestion,
    nodes: WbsNode[],
    tasks: TaskCompact[],
    projectId: number,
): SuggestionPreview {
    const now = new Date().toISOString();
    const idByTempId = new Map<string, number>();
    suggestion.nodes.forEach((node, index) => idByTempId.set(node.temp_id, -(index + 1)));

    const draftNodes: WbsNode[] = suggestion.nodes.map((node, index) => ({
        id: idByTempId.get(node.temp_id) as number,
        project_id: projectId,
        parent_id:
            node.parent_temp_id === null
                ? null
                : (idByTempId.get(node.parent_temp_id) ?? null),
        title: node.title,
        position: (index + 1) * DRAFT_POSITION_STEP,
        created_at: now,
        updated_at: now,
    }));

    const positionByTask = new Map<number, { nodeId: number; position: number }>();
    const countByNode = new Map<string, number>();
    for (const assignment of suggestion.assignments) {
        const nodeId = idByTempId.get(assignment.node_temp_id);
        if (nodeId === undefined) {
            continue;
        }
        const order = (countByNode.get(assignment.node_temp_id) ?? 0) + 1;
        countByNode.set(assignment.node_temp_id, order);
        positionByTask.set(assignment.task_id, {
            nodeId,
            position: order * DRAFT_POSITION_STEP,
        });
    }

    return {
        nodes: [...nodes, ...draftNodes],
        tasks: tasks.map((task) => {
            const placement = positionByTask.get(task.id);
            return placement === undefined
                ? task
                : {
                      ...task,
                      wbs_node_id: placement.nodeId,
                      wbs_position: placement.position,
                      canvas_x: null,
                      canvas_y: null,
                  };
        }),
    };
}

/**
 * Убирает раздел черновика вместе с его подразделами.
 *
 * Задачи удалённой ветки не пропадают: они просто перестают участвовать в
 * предложении и останутся там, где лежат сейчас.
 */
export function removeSuggestedNode(suggestion: WbsSuggestion, tempId: string): WbsSuggestion {
    const removed = new Set<string>([tempId]);
    let changed = true;
    while (changed) {
        changed = false;
        for (const node of suggestion.nodes) {
            if (
                node.parent_temp_id !== null &&
                removed.has(node.parent_temp_id) &&
                !removed.has(node.temp_id)
            ) {
                removed.add(node.temp_id);
                changed = true;
            }
        }
    }

    const dropped = suggestion.assignments.filter((item) => removed.has(item.node_temp_id));
    return {
        ...suggestion,
        nodes: suggestion.nodes.filter((node) => !removed.has(node.temp_id)),
        assignments: suggestion.assignments.filter((item) => !removed.has(item.node_temp_id)),
        skipped_task_ids: [
            ...suggestion.skipped_task_ids,
            ...dropped.map((item) => item.task_id),
        ],
    };
}
