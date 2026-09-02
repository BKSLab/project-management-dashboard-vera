import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { AlertTriangle, CalendarDays, Check, Clock3 } from "lucide-react";
import { calendarTaskDragId } from "@/lib/calendar";
import { cn } from "@/lib/cn";
import type { CalendarTask as CalendarTaskModel } from "@/lib/types";
import { IconButton } from "@/components/ui/Button";

interface CalendarTaskProps {
    task: CalendarTaskModel;
    stageName?: string;
    compact?: boolean;
    draggable?: boolean;
    onOpen: (taskId: number) => void;
    onSchedule?: (task: CalendarTaskModel) => void;
}

/** Компактное временное представление той же Task, что открывается в общем Drawer. */
export function CalendarTask({
    task,
    stageName,
    compact = false,
    draggable = false,
    onOpen,
    onSchedule,
}: CalendarTaskProps) {
    const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
        id: calendarTaskDragId(task.id),
        data: { task, dragKind: task.due_date === null ? "unscheduled" : "deadline" },
        disabled: !draggable,
    });
    const stateLabel = task.is_done
        ? "Завершена"
        : task.is_overdue
          ? "Просрочена"
          : task.is_due_soon
            ? "Срок близко"
            : "Запланирована";
    const icon = task.is_done ? (
        <Check size={11} aria-hidden="true" />
    ) : task.is_overdue ? (
        <AlertTriangle size={11} aria-hidden="true" />
    ) : task.is_due_soon ? (
        <Clock3 size={11} aria-hidden="true" />
    ) : null;
    const riskDetails = task.risk_reasons.map((reason) => reason.message).join(" · ");

    return (
        <div
            className="flex min-w-0 items-center gap-1"
            style={{ opacity: isDragging ? 0.35 : undefined }}
        >
            <button
                ref={setNodeRef}
                type="button"
                onClick={() => onOpen(task.id)}
                title={`${task.key} · ${task.title}\n${stageName ?? "Стадия не найдена"} · ${stateLabel}${riskDetails ? `\n${riskDetails}` : ""}`}
                aria-label={`Открыть ${task.key}: ${task.title}. ${stateLabel}${riskDetails ? `. ${riskDetails}` : ""}`}
                className={cn(
                    "group flex min-w-0 flex-1 items-center gap-1 rounded-md border px-1.5 text-left",
                    "transition-[background-color,border-color,color,box-shadow]",
                    "duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
                    compact ? "h-6" : "min-h-7 py-1",
                    draggable && "cursor-grab touch-none active:cursor-grabbing",
                    task.is_done && "border-line-subtle bg-surface-2/55 text-muted",
                    task.is_overdue && "border-danger/35 bg-danger/10 text-danger hover:bg-danger/15",
                    !task.is_done &&
                        !task.is_overdue &&
                        task.is_due_soon &&
                        "border-warning/35 bg-warning/10 text-warning hover:bg-warning/15",
                    !task.is_done &&
                        !task.is_overdue &&
                        !task.is_due_soon &&
                        "border-line bg-elevated text-secondary hover:border-line-strong hover:text-primary",
                )}
                style={{ transform: CSS.Translate.toString(transform) }}
                {...(draggable ? attributes : {})}
                {...(draggable ? listeners : {})}
            >
                <span className="shrink-0">{icon}</span>
                <span className="shrink-0 font-mono text-[10px] opacity-80">{task.key}</span>
                {!compact && <span className="truncate text-[11px]">{task.title}</span>}
            </button>
            {!compact && onSchedule && (
                <IconButton
                    size="sm"
                    label={`Изменить срок ${task.key}`}
                    onClick={() => onSchedule(task)}
                >
                    <CalendarDays size={12} aria-hidden="true" />
                </IconButton>
            )}
        </div>
    );
}
