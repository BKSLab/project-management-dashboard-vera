import { useDroppable } from "@dnd-kit/core";
import { useDraggable } from "@dnd-kit/core";
import type { ProjectStage, Task } from "@/lib/types";
import { cn } from "@/lib/cn";
import { StatusDot } from "@/components/ui/Badge";
import { TaskCard } from "@/components/kanban/TaskCard";

function DraggableTask({
    task,
    riskCount,
    isDone,
    isSelected,
    onOpen,
}: {
    task: Task;
    riskCount: number;
    isDone: boolean;
    isSelected: boolean;
    onOpen: (taskId: number) => void;
}) {
    const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: task.id });

    return (
        <TaskCard
            ref={setNodeRef}
            task={task}
            riskCount={riskCount}
            isDone={isDone}
            isSelected={isSelected}
            className={cn(isDragging && "opacity-40")}
            onOpen={onOpen}
            dragHandleProps={{ ...listeners, ...attributes }}
        />
    );
}

interface ColumnProps {
    riskCounts: Record<string, number>;
    stage: ProjectStage;
    tasks: Task[];
    selectedTaskId: number | null;
    onTaskOpen: (taskId: number) => void;
}

/**
 * Колонка доски: лёгкая шапка со счётчиком и цветным маркером стадии.
 * Колонка не заливается цветом статуса (раздел 7 дизайн-гайда).
 */
export function Column({ stage, tasks, selectedTaskId, onTaskOpen, riskCounts }: ColumnProps) {
    const { setNodeRef, isOver } = useDroppable({ id: stage.id });

    return (
        <section
            aria-label={`Колонка ${stage.name}`}
            className="flex w-[min(88vw,300px)] shrink-0 flex-col"
        >
            <header className="mb-2 flex items-center gap-2 px-1">
                <StatusDot color={stage.color} />
                <h2 className="text-[12px] font-semibold tracking-[0.04em] text-secondary uppercase">
                    {stage.name}
                </h2>
                <span className="font-mono text-[11px] text-disabled">{tasks.length}</span>
            </header>

            <div
                ref={setNodeRef}
                className={cn(
                    "scrollbar-thin flex min-h-40 flex-1 flex-col gap-2 overflow-y-auto rounded-lg p-1.5",
                    "border transition-[background-color,border-color] duration-[var(--duration-fast)]",
                    isOver
                        ? "border-dashed border-accent-border bg-accent/[0.055]"
                        : "border-transparent bg-surface/35",
                )}
            >
                {tasks.map((task) => (
                    <DraggableTask
                        key={task.id}
                        task={task}
                        riskCount={riskCounts[task.id] ?? 0}
                        isDone={stage.is_done_stage}
                        isSelected={task.id === selectedTaskId}
                        onOpen={onTaskOpen}
                    />
                ))}
                {tasks.length === 0 && (
                    <p className="px-2 py-6 text-center text-[12px] text-disabled">Пусто</p>
                )}
            </div>
        </section>
    );
}
