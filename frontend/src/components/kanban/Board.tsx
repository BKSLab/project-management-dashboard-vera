import { useMemo, useState } from "react";
import {
    DndContext,
    DragOverlay,
    PointerSensor,
    useSensor,
    useSensors,
    type DragEndEvent,
    type DragStartEvent,
} from "@dnd-kit/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { KanbanStage, KanbanTask } from "@/lib/types";
import { compareWbsCode } from "@/lib/sortCode";
import { Column } from "@/components/kanban/Column";
import { TaskCardContent } from "@/components/kanban/TaskCard";

interface BoardProps {
    stages: KanbanStage[];
    tasks: KanbanTask[];
    highlightedTaskId: number | null;
    onTaskClick: (taskId: number) => void;
}

interface MoveVariables {
    taskId: number;
    stageId: number;
    position: number;
}

export function Board({ stages, tasks, highlightedTaskId, onTaskClick }: BoardProps) {
    const queryClient = useQueryClient();
    const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));
    const [activeTask, setActiveTask] = useState<KanbanTask | null>(null);

    const backlogStageId = useMemo(
        () =>
            stages.length > 0
                ? stages.reduce((min, stage) => (stage.order_index < min.order_index ? stage : min)).id
                : null,
        [stages]
    );

    const tasksByStage = useMemo(() => {
        const map = new Map<number, KanbanTask[]>();
        for (const stage of stages) map.set(stage.id, []);
        for (const task of tasks) {
            map.get(task.stage_id)?.push(task);
        }
        for (const [stageId, list] of map.entries()) {
            if (stageId === backlogStageId) {
                list.sort((a, b) => {
                    if (a.wbs_code && b.wbs_code) return compareWbsCode(a.wbs_code, b.wbs_code);
                    if (a.wbs_code) return -1;
                    if (b.wbs_code) return 1;
                    return a.title.localeCompare(b.title, "ru");
                });
            } else {
                list.sort((a, b) => a.position - b.position);
            }
        }
        return map;
    }, [stages, tasks, backlogStageId]);

    const moveMutation = useMutation({
        mutationFn: ({ taskId, stageId, position }: MoveVariables) =>
            api.patch<KanbanTask>(`/api/kanban/tasks/${taskId}/move`, { stage_id: stageId, position }),
        onMutate: async (variables) => {
            const previous = queryClient.getQueryData<KanbanTask[]>(["kanban", "tasks"]);
            queryClient.setQueryData<KanbanTask[]>(["kanban", "tasks"], (old) =>
                (old ?? []).map((task) =>
                    task.id === variables.taskId
                        ? { ...task, stage_id: variables.stageId, position: variables.position }
                        : task
                )
            );
            return { previous };
        },
        onError: (_error, _variables, context) => {
            if (context?.previous) {
                queryClient.setQueryData(["kanban", "tasks"], context.previous);
            }
        },
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: ["kanban", "tasks"] });
            queryClient.invalidateQueries({ queryKey: ["wbs", "tree"] });
        },
    });

    function handleDragStart(event: DragStartEvent) {
        const task = tasks.find((item) => item.id === Number(event.active.id));
        setActiveTask(task ?? null);
    }

    function handleDragEnd(event: DragEndEvent) {
        setActiveTask(null);
        const { active, over } = event;
        if (!over) return;

        const activeTaskId = Number(active.id);
        const activeTask = tasks.find((task) => task.id === activeTaskId);
        if (!activeTask) return;

        const targetStageId = Number(over.id);
        if (targetStageId === activeTask.stage_id) return;

        const destTasks = tasksByStage.get(targetStageId) ?? [];
        const maxPosition = destTasks.reduce((max, task) => Math.max(max, task.position), 0);
        const newPosition = maxPosition + 1000;

        moveMutation.mutate({ taskId: activeTaskId, stageId: targetStageId, position: newPosition });
    }

    return (
        <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragCancel={() => setActiveTask(null)}
        >
            <div className="scrollbar-thin flex justify-center gap-4 overflow-x-auto pb-4">
                {stages.map((stage) => (
                    <Column
                        key={stage.id}
                        stage={stage}
                        tasks={tasksByStage.get(stage.id) ?? []}
                        highlightedTaskId={highlightedTaskId}
                        onTaskClick={onTaskClick}
                        groupByPhase={stage.id === backlogStageId}
                    />
                ))}
            </div>
            <DragOverlay>
                {activeTask && (
                    <div className="w-80 rotate-1 scale-[1.03] rounded-xl border border-accent/30 bg-surface-elevated p-3 text-sm shadow-[var(--shadow-dragging)]">
                        <TaskCardContent task={activeTask} />
                    </div>
                )}
            </DragOverlay>
        </DndContext>
    );
}
