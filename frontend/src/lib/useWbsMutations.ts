import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import { useToast } from "@/lib/toast";
import type { TaskCompact, WbsNode, WbsNodeDeleteResult, WbsStructure } from "@/lib/types";

interface MoveNodeVariables {
    nodeId: number;
    parentId: number | null;
    beforeId: number | null;
}

interface AssignVariables {
    taskId: number;
    wbsNodeId: number | null;
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

    const assignTask = useMutation({
        mutationFn: ({ taskId, wbsNodeId }: AssignVariables) =>
            wbsNodeId === null
                ? api.delete<TaskCompact>(endpoints.wbsTaskAssignment(projectId, taskId))
                : api.post<TaskCompact>(endpoints.wbsTaskAssign(projectId, taskId), {
                      wbs_node_id: wbsNodeId,
                  }),
        onMutate: (variables) =>
            optimistic((current) => ({
                ...current,
                tasks: current.tasks.map((task) =>
                    task.id === variables.taskId
                        ? { ...task, wbs_node_id: variables.wbsNodeId }
                        : task,
                ),
            })),
        onError: (error, _variables, context) =>
            rollback(context, `Не удалось переместить задачу: ${(error as Error).message}`),
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: structureKey });
            invalidateAll();
        },
    });

    return { createNode, renameNode, moveNode, deleteNode, assignTask };
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
