import type { DashboardTask } from "@/lib/types";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/dates";
import { DueDate } from "@/components/ui/DueDate";
import { PriorityBadge, StatusDot } from "@/components/ui/Badge";

interface TaskRowProps {
    task: DashboardTask;
    /** Вместо срока показывает время последнего изменения. */
    showUpdated?: boolean;
    onOpen: (taskId: number) => void;
}

/** Строка задачи в сводке дашборда: одна сущность — один визуальный язык. */
export function TaskRow({ task, showUpdated = false, onOpen }: TaskRowProps) {
    return (
        <button
            type="button"
            onClick={() => onOpen(task.id)}
            className={cn(
                "flex w-full min-w-0 items-center gap-3 rounded-md px-2.5 py-2 text-left",
                "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
                "hover:bg-hover",
            )}
        >
            <StatusDot color={task.project_color} />
            <span className="w-20 shrink-0 truncate font-mono text-[11px] text-muted">
                {task.key}
            </span>
            <span className="min-w-0 flex-1 truncate text-[13px] text-secondary">{task.title}</span>
            <span className="hidden shrink-0 text-[11px] text-muted sm:inline">
                {task.stage_name}
            </span>
            <PriorityBadge priority={task.priority} className="hidden shrink-0 sm:inline-flex" />
            {showUpdated ? (
                <span className="w-24 shrink-0 text-right text-[11px] text-muted">
                    {formatRelative(task.updated_at)}
                </span>
            ) : (
                <span className="w-24 shrink-0 text-right">
                    <DueDate value={task.due_date} />
                </span>
            )}
        </button>
    );
}
