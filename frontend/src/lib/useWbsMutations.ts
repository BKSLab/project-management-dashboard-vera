import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import { useToast } from "@/lib/toast";
import type {
    TaskCompact,
    WbsNode,
    WbsNodeDeleteResult,
    WbsStructure,
    WbsSuggestedAssignment,
    WbsSuggestedNode,
    WbsSuggestion,
    WbsSuggestionApplyResult,
} from "@/lib/types";

interface MoveNodeVariables {
    nodeId: number;
    parentId: number | null;
    beforeId: number | null;
}

/**
 * Одна операция для всех трёх состояний задачи: раздел ИСР, свободный холст
 * и список-пул. Раздел и координаты взаимоисключающи — место задачи внутри
 * структуры считает раскладка.
 */
export interface PlaceTaskVariables {
    taskId: number;
    wbsNodeId: number | null;
    /** Задача раздела, перед которой встаёт перемещаемая; null — в конец. */
    beforeTaskId?: number | null;
    canvasX?: number | null;
    canvasY?: number | null;
}

/**
 * Мутации структуры с оптимистичным обновлением и откатом (§41 ТЗ).
 * Все они правят один кэш `wbs`, поэтому карта перестраивается мгновенно,
 * а расхождение с сервером исправляется инвалидацией.
 */
export function useWbsMutations(projectId: number) {
    const queryClient = useQueryClient();
    const toast = useToast();
    const structureKey = queryKeys.wbs(projectId);

    async function optimistic(update: (current: WbsStructure) => WbsStructure) {
        await queryClient.cancelQueries({ queryKey: structureKey });
        const previous = queryClient.getQueryData<WbsStructure>(structureKey);
        if (previous) {
            queryClient.setQueryData<WbsStructure>(structureKey, update(previous));
        }
        return { previous };
    }

    function rollback(context: { previous?: WbsStructure } | undefined, message: string) {
        if (context?.previous) {
            queryClient.setQueryData(structureKey, context.previous);
        }
        toast.error(message);
    }

    /** Структура влияет на показатели проекта и общий дашборд. */
    function invalidateAll() {
        queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    }

    const createNode = useMutation({
        mutationFn: (variables: { title: string; parentId: number | null }) =>
            api.post<WbsNode>(endpoints.wbsNodes(projectId), {
                title: variables.title,
                parent_id: variables.parentId,
            }),
        onError: (error) => toast.error(`Не удалось создать раздел: ${(error as Error).message}`),
        onSettled: invalidateAll,
    });

    const renameNode = useMutation({
        mutationFn: (variables: { nodeId: number; title: string }) =>
            api.patch<WbsNode>(endpoints.wbsNode(projectId, variables.nodeId), {
                title: variables.title,
            }),
        onMutate: (variables) =>
            optimistic((current) => ({
                ...current,
                nodes: current.nodes.map((node) =>
                    node.id === variables.nodeId ? { ...node, title: variables.title } : node,
                ),
            })),
        onError: (error, _variables, context) =>
            rollback(context, `Не удалось переименовать раздел: ${(error as Error).message}`),
        onSettled: invalidateAll,
    });

    const moveNode = useMutation({
        mutationFn: (variables: MoveNodeVariables) =>
            api.post<WbsNode>(endpoints.wbsNodeMove(projectId, variables.nodeId), {
                parent_id: variables.parentId,
                before_id: variables.beforeId,
            }),
        onMutate: (variables) =>
            optimistic((current) => ({
                ...current,
                nodes: current.nodes.map((node) =>
                    node.id === variables.nodeId
                        ? {
                              ...node,
                              parent_id: variables.parentId,
                              position: predictPosition(current.nodes, variables),
                          }
                        : node,
                ),
            })),
        onError: (error, _variables, context) =>
            rollback(context, `Не удалось перенести раздел: ${(error as Error).message}`),
        onSuccess: (node) => {
            // Итоговую позицию считает backend, поэтому берём её из ответа.
            queryClient.setQueryData<WbsStructure>(structureKey, (current) =>
                current
                    ? {
                          ...current,
                          nodes: current.nodes.map((item) => (item.id === node.id ? node : item)),
                      }
                    : current,
            );
        },
        onSettled: invalidateAll,
    });

    const deleteNode = useMutation({
        mutationFn: (nodeId: number) =>
            api.delete<WbsNodeDeleteResult>(endpoints.wbsNode(projectId, nodeId)),
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: structureKey });
            toast.success(
                result.released_tasks > 0
                    ? `Раздел удалён, задач возвращено в пул: ${result.released_tasks}`
                    : "Раздел удалён",
            );
        },
        onError: (error) => toast.error(`Не удалось удалить раздел: ${(error as Error).message}`),
        onSettled: invalidateAll,
    });

    const placeTask = useMutation({
        mutationFn: (variables: PlaceTaskVariables) =>
            api.post<TaskCompact>(endpoints.wbsTaskPlacement(projectId, variables.taskId), {
                wbs_node_id: variables.wbsNodeId,
                before_task_id: variables.beforeTaskId ?? null,
                canvas_x: variables.canvasX ?? null,
                canvas_y: variables.canvasY ?? null,
            }),
        onMutate: (variables) =>
            optimistic((current) => ({
                ...current,
                tasks: current.tasks.map((task) =>
                    task.id === variables.taskId ? applyPlacement(current, task, variables) : task,
                ),
            })),
        onError: (error, _variables, context) =>
            rollback(context, `Не удалось переместить задачу: ${(error as Error).message}`),
        onSuccess: (task) => {
            // Итоговую позицию внутри раздела считает backend.
            queryClient.setQueryData<WbsStructure>(structureKey, (current) =>
                current
                    ? {
                          ...current,
                          tasks: current.tasks.map((item) => (item.id === task.id ? task : item)),
                      }
                    : current,
            );
        },
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: structureKey });
            invalidateAll();
        },
    });

    /** Черновик ИСР: запрос ничего не меняет в проекте, кэш не трогаем. */
    const suggest = useMutation({
        mutationFn: () => api.post<WbsSuggestion>(endpoints.wbsSuggestion(projectId), {}),
        onError: (error) =>
            toast.error(`Не удалось предложить структуру: ${(error as Error).message}`),
    });

    const applySuggestion = useMutation({
        mutationFn: (variables: { nodes: WbsSuggestedNode[]; assignments: WbsSuggestedAssignment[] }) =>
            api.post<WbsSuggestionApplyResult>(endpoints.wbsSuggestionApply(projectId), variables),
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: structureKey });
            toast.success(
                `Структура применена: разделов ${result.created_nodes}, задач ${result.assigned_tasks}`,
            );
        },
        onError: (error) =>
            toast.error(`Не удалось применить структуру: ${(error as Error).message}`),
        onSettled: invalidateAll,
    });

    return { createNode, renameNode, moveNode, deleteNode, placeTask, suggest, applySuggestion };
}

/**
 * Оптимистичный результат перемещения задачи. Точную позицию внутри раздела
 * вернёт backend, здесь важно лишь не дать карточке «прыгнуть» до ответа.
 */
function applyPlacement(
    structure: WbsStructure,
    task: TaskCompact,
    variables: PlaceTaskVariables,
): TaskCompact {
    if (variables.wbsNodeId === null) {
        return {
            ...task,
            wbs_node_id: null,
            wbs_position: null,
            canvas_x: variables.canvasX ?? null,
            canvas_y: variables.canvasY ?? null,
        };
    }
    const siblings = structure.tasks
        .filter((item) => item.wbs_node_id === variables.wbsNodeId && item.id !== task.id)
        .sort((first, second) => (first.wbs_position ?? 0) - (second.wbs_position ?? 0));
    const index =
        variables.beforeTaskId == null
            ? siblings.length
            : siblings.findIndex((item) => item.id === variables.beforeTaskId);
    const next = index < 0 ? siblings.length : index;
    const previousPosition = next === 0 ? 0 : (siblings[next - 1].wbs_position ?? 0);
    const nextPosition = siblings[next]?.wbs_position ?? previousPosition + 2000;
    return {
        ...task,
        wbs_node_id: variables.wbsNodeId,
        wbs_position: (previousPosition + nextPosition) / 2,
        canvas_x: null,
        canvas_y: null,
    };
}

/**
 * Приблизительная позиция для оптимистичного шага: точное значение вернёт
 * backend, здесь важно лишь сохранить правильный порядок до ответа.
 */
function predictPosition(nodes: WbsNode[], variables: MoveNodeVariables): number {
    const siblings = nodes
        .filter((node) => node.parent_id === variables.parentId && node.id !== variables.nodeId)
        .sort((first, second) => first.position - second.position || first.id - second.id);

    if (variables.beforeId === null) {
        const last = siblings.at(-1);
        return last === undefined ? 1000 : last.position + 1000;
    }
    const index = siblings.findIndex((node) => node.id === variables.beforeId);
    if (index < 0) {
        const last = siblings.at(-1);
        return last === undefined ? 1000 : last.position + 1000;
    }
    const next = siblings[index].position;
    const previous = index === 0 ? 0 : siblings[index - 1].position;
    return (previous + next) / 2;
}
