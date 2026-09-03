import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Unlink } from "lucide-react";
import { cn } from "@/lib/cn";
import type { ProjectStage, TaskCompact } from "@/lib/types";
import { DueDate } from "@/components/ui/DueDate";
import { PriorityBadge, StatusDot } from "@/components/ui/Badge";

export interface TaskNodeData {
    task: TaskCompact;
    stage: ProjectStage | undefined;
    detail: "full" | "compact" | "minimal";
    /** Карточка лежит на холсте и ещё не связана с разделом. */
    isFloating: boolean;
    /** Карточка входит в предложенную ИИ структуру и пока не сохранена. */
    isDraft: boolean;
    onContextMenu: (taskId: number, anchor: { x: number; y: number }) => void;
}

/**
 * Задача внутри ИСР (§22 ТЗ): компактный узел, а не карточка канбана — так на
 * экране помещается заметно больше работ.
 *
 * Карточку можно таскать по холсту: пока от раздела к ней не идёт стрелка,
 * она лежит вне структуры и в проекте ничего не занимает. Клик открывает
 * панель задачи — его обрабатывает canvas, чтобы отличить клик от перетаскивания.
 */
export function TaskNode({ data, selected }: NodeProps) {
    const { task, stage, detail, isFloating, isDraft, onContextMenu } =
        data as unknown as TaskNodeData;

    return (
        <div
            onContextMenu={(event) => {
                event.preventDefault();
                onContextMenu(task.id, { x: event.clientX, y: event.clientY });
            }}
            className={cn(
                "flex h-full w-full cursor-grab flex-col justify-center gap-1 rounded-[var(--radius-control)] border px-2.5 py-2 text-left",
                "transition-[background-color,border-color,box-shadow] duration-[var(--duration-normal)]",
                "ease-[var(--ease-standard)] shadow-card active:cursor-grabbing",
                isDraft ? "bg-accent/[0.06]" : "bg-surface",
                selected
                    ? "border-accent/60 bg-elevated shadow-selected"
                    : isDraft
                      ? "border-dashed border-accent/55"
                      : isFloating
                        ? "border-dashed border-line"
                        : "border-line-subtle hover:border-line hover:bg-surface-2",
            )}
        >
            <Handle
                type="target"
                id="left"
                position={Position.Left}
                className="!size-2 !border-0 !bg-accent !opacity-0 hover:!opacity-100"
            />
            <Handle
                type="target"
                id="top"
                position={Position.Top}
                className="!opacity-0"
                isConnectable={false}
            />

            <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[10px] text-muted">{task.key}</span>
                <div className="flex items-center gap-1">
                    {isFloating && (
                        <Unlink
                            size={10}
                            aria-label="Задача вне структуры"
                            className="text-disabled"
                        />
                    )}
                    <PriorityBadge priority={task.priority} />
                </div>
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
        </div>
    );
}
