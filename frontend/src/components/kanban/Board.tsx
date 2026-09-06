import { useMemo, useState } from "react";
import {
    DndContext,
    DragOverlay,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    type DragEndEvent,
    type DragStartEvent,
} from "@dnd-kit/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { ProjectStage, Task } from "@/lib/types";
import { useToast } from "@/lib/toast";
import { useRiskTaskCounts } from "@/lib/useRisks";
import { Column } from "@/components/kanban/Column";
import { TaskCard } from "@/components/kanban/TaskCard";

const POSITION_STEP = 1000;

interface BoardProps {
    projectId: number;
    stages: ProjectStage[];
    tasks: Task[];
    search: string;
    selectedTaskId: number | null;
    onTaskOpen: (taskId: number) => void;
}

interface MoveVariables {
    taskId: number;
    stageId: number;
    position: number;
}

export function Board({
    projectId,
    stages,
    tasks,
    search,
    selectedTaskId,
    onTaskOpen,
}: BoardProps) {
    const queryClient = useQueryClient();
    const riskCounts = useRiskTaskCounts(projectId);
    const toast = useToast();
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
        useSensor(KeyboardSensor),
    );
    const [activeTask, setActiveTask] = useState<Task | null>(null);

    const tasksByStage = useMemo(() => {
        const map = new Map<number, Task[]>();
        for (const stage of stages) {
            map.set(stage.id, []);
        }
        for (const task of tasks) {
            map.get(task.stage_id)?.push(task);
        }
        for (const list of map.values()) {
            list.sort((first, second) => first.position - second.position);
        }
        return map;
    }, [stages, tasks]);

    const tasksKey = queryKeys.tasks(projectId, search);

    const moveMutation = useMutation({
        mutationFn: ({ taskId, stageId, position }: MoveVariables) =>
            api.patch<Task>(endpoints.taskMove(taskId), { stage_id: stageId, position }),
        onMutate: async (variables) => {
            await queryClient.cancelQueries({ queryKey: tasksKey });
            const previous = queryClient.getQueryData<Task[]>(tasksKey);
            queryClient.setQueryData<Task[]>(tasksKey, (old) =>
                (old ?? []).map((task) =>
                    task.id === variables.taskId
                        ? { ...task, stage_id: variables.stageId, position: variables.position }
                        : task,
                ),
            );
            return { previous };
        },
        onError: (error, _variables, context) => {
            if (context?.previous) {
                queryClient.setQueryData(tasksKey, context.previous);
            }
            toast.error(`Не удалось переместить задачу: ${(error as Error).message}`);
        },
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
            queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
        },
    });

    function handleDragStart(event: DragStartEvent) {
        setActiveTask(tasks.find((task) => task.id === Number(event.active.id)) ?? null);
    }

    function handleDragEnd(event: DragEndEvent) {
        setActiveTask(null);
        const { active, over } = event;
        if (!over) {
            return;
        }
        const task = tasks.find((item) => item.id === Number(active.id));
        const targetStageId = Number(over.id);
        if (!task || targetStageId === task.stage_id) {
            return;
        }
        const destination = tasksByStage.get(targetStageId) ?? [];
        const maxPosition = destination.reduce((max, item) => Math.max(max, item.position), 0);
        moveMutation.mutate({
            taskId: task.id,
            stageId: targetStageId,
            position: maxPosition + POSITION_STEP,
        });
    }

    return (
        <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragCancel={() => setActiveTask(null)}
        >
            <div className="scrollbar-thin h-full overflow-x-auto px-5 py-4">
                <div className="flex h-full w-max min-w-full items-start gap-3">
                    {stages.map((stage) => (
                        <Column
                            key={stage.id}
                            stage={stage}
                            riskCounts={riskCounts.data ?? {}}
                            tasks={tasksByStage.get(stage.id) ?? []}
                            selectedTaskId={selectedTaskId}
                            onTaskOpen={onTaskOpen}
                        />
                    ))}
                </div>
            </div>

            <DragOverlay>
                {activeTask && (
                    <div className="w-[300px]">
                        <TaskCard task={activeTask} riskCount={riskCounts.data?.[activeTask.id] ?? 0} isDragging onOpen={() => undefined} />
                    </div>
                )}
            </DragOverlay>
        </DndContext>
    );
}
