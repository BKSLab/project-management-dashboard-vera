import { useDroppable } from "@dnd-kit/core";
import type { KanbanStage, KanbanTask } from "@/lib/types";
import { TaskCard } from "@/components/kanban/TaskCard";
import { cn } from "@/lib/cn";

interface ColumnProps {
    stage: KanbanStage;
    tasks: KanbanTask[];
    highlightedTaskId: number | null;
    onTaskClick: (taskId: number) => void;
    groupByPhase?: boolean;
}

interface RenderItem {
    type: "header" | "task";
    phaseName?: string;
    task?: KanbanTask;
}

function buildRenderItems(tasks: KanbanTask[], groupByPhase: boolean): RenderItem[] {
    if (!groupByPhase) {
        return tasks.map((task) => ({ type: "task", task }));
    }

    const items: RenderItem[] = [];
    let lastPhase: string | null = "__unset__";
    for (const task of tasks) {
        const phase = task.wbs_phase_name ?? "Без фазы (вручную)";
        if (phase !== lastPhase) {
            items.push({ type: "header", phaseName: phase });
            lastPhase = phase;
        }
        items.push({ type: "task", task });
    }
    return items;
}

export function Column({ stage, tasks, highlightedTaskId, onTaskClick, groupByPhase = false }: ColumnProps) {
    const { setNodeRef, isOver } = useDroppable({
        id: stage.id,
        data: { type: "column" },
    });

    const widthClass = tasks.length > 50
        ? "w-[calc(100vw-2rem)] sm:w-[26rem]"
        : "w-[calc(100vw-2rem)] sm:w-80";
    const renderItems = buildRenderItems(tasks, groupByPhase);

    return (
        <div className={cn("flex h-[75vh] shrink-0 flex-col rounded-2xl border border-white/[0.05] bg-surface", widthClass)}>
            <div
                className="flex items-center justify-between gap-2 border-b-2 px-4 py-3"
                style={{ borderBottomColor: stage.color }}
            >
                <span className="text-sm font-semibold uppercase tracking-[0.1em] text-foreground">{stage.name}</span>
                <span className="text-xs text-muted">{tasks.length} задач</span>
            </div>

            <div
                ref={setNodeRef}
                className={cn(
                    "scrollbar-thin flex flex-1 flex-col gap-2 overflow-y-auto p-4",
                    isOver && "rounded-b-2xl border border-accent/30 bg-accent/[0.08]"
                )}
            >
                {renderItems.map((item, index) =>
                    item.type === "header" ? (
                        <p
                            key={`header-${index}`}
                            className="mt-1 truncate px-1 text-[11px] font-bold uppercase tracking-wider text-muted first:mt-0"
                        >
                            {item.phaseName}
                        </p>
                    ) : (
                        <TaskCard
                            key={item.task!.id}
                            task={item.task!}
                            highlighted={item.task!.id === highlightedTaskId}
                            onClick={() => onTaskClick(item.task!.id)}
                        />
                    )
                )}
            </div>
        </div>
    );
}
