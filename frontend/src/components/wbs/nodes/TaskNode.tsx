import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/cn";
import type { ProjectStage, TaskCompact } from "@/lib/types";
import { DueDate } from "@/components/ui/DueDate";
import { PriorityBadge, StatusDot } from "@/components/ui/Badge";

export interface TaskNodeData {
    task: TaskCompact;
    stage: ProjectStage | undefined;
    detail: "full" | "compact" | "minimal";
    onOpen: (taskId: number) => void;
    onContextMenu: (taskId: number, anchor: { x: number; y: number }) => void;
}

/**
 * Задача внутри ИСР (§22 ТЗ): компактный узел, а не карточка канбана —
 * так на экране помещается заметно больше работ. Клик открывает ту же
 * панель задачи, отдельного редактора для карты нет.
 */
export function TaskNode({ data, selected }: NodeProps) {
    const { task, stage, detail, onOpen, onContextMenu } = data as unknown as TaskNodeData;

    return (
        <button
            type="button"
            onClick={() => onOpen(task.id)}
            onContextMenu={(event) => {
                event.preventDefault();
                onContextMenu(task.id, { x: event.clientX, y: event.clientY });
            }}
            className={cn(
                "flex h-full w-full flex-col justify-center gap-1 rounded-[10px] border bg-elevated px-2.5 py-2 text-left",
                "transition-[background-color,border-color,box-shadow] duration-[var(--duration-normal)]",
                "ease-[var(--ease-standard)] shadow-[0_1px_2px_rgba(0,0,0,0.28)]",
                selected
                    ? "border-[rgba(88,166,255,0.65)] shadow-[0_0_0_1px_rgba(88,166,255,0.15)]"
                    : "border-line-subtle hover:border-line-strong",
            )}
        >
            <Handle type="target" position={Position.Left} className="!opacity-0" isConnectable={false} />

            <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[10px] text-muted">{task.key}</span>
                <PriorityBadge priority={task.priority} />
            </div>

            <p
                className={cn(
                    "line-clamp-1 text-[12px] leading-snug",
                    task.is_done ? "text-muted line-through" : "text-secondary",
                )}
            >
                {task.title}
            </p>

            {detail === "full" && (
                <div className="flex items-center justify-between gap-2 text-[10px] text-muted">
                    {stage && (
                        <span className="inline-flex min-w-0 items-center gap-1">
                            <StatusDot color={stage.color} />
                            <span className="truncate">{stage.name}</span>
                        </span>
                    )}
                    <DueDate value={task.due_date} isDone={task.is_done} />
                </div>
            )}
        </button>
    );
}
