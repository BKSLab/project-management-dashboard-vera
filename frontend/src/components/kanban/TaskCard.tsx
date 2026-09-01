import { forwardRef } from "react";
import { MessageSquare } from "lucide-react";
import type { Task } from "@/lib/types";
import { cn } from "@/lib/cn";
import { PriorityBadge } from "@/components/ui/Badge";
import { DueDate } from "@/components/ui/DueDate";
import { SearchHighlight } from "@/components/ui/SearchHighlight";

/** Убирает разметку Markdown: в карточке показываем текст, а не сырой синтаксис. */
function toPlainText(markdown: string): string {
    return markdown
        .replace(/```[\s\S]*?```/g, " ")
        .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
        .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
        .replace(/[#>*_`~-]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

interface TaskCardProps {
    task: Task;
    breadcrumb?: string | null;
    isDone?: boolean;
    isSelected?: boolean;
    isDragging?: boolean;
    onOpen: (taskId: number) => void;
    className?: string;
    style?: React.CSSProperties;
    dragHandleProps?: Record<string, unknown>;
}

/**
 * Карточка канбана по макету раздела 8: понятна без открытия и остаётся
 * компактной. Отсутствующие данные не оставляют пустых блоков.
 */
export const TaskCard = forwardRef<HTMLDivElement, TaskCardProps>(function TaskCard(
    {
        task,
        breadcrumb,
        isDone = false,
        isSelected = false,
        isDragging = false,
        onOpen,
        className,
        style,
        dragHandleProps,
    },
    ref,
) {
    const description = task.description_md ? toPlainText(task.description_md) : "";

    return (
        <div
            ref={ref}
            style={style}
            {...dragHandleProps}
            className={cn(
                "group rounded-[var(--radius-md)] border bg-elevated shadow-card",
                "transition-[background-color,border-color,box-shadow,transform]",
                "duration-[var(--duration-normal)] ease-[var(--ease-standard)]",
                isSelected
                    ? "border-accent-border shadow-[0_0_0_1px_rgba(88,166,255,0.12)]"
                    : "border-line",
                !isDragging && "hover:-translate-y-px hover:border-line-strong hover:shadow-elevated",
                isDragging && "rotate-[0.5deg] scale-[1.015] shadow-dragging",
                className,
            )}
        >
            <button
                type="button"
                onClick={() => onOpen(task.id)}
                className="flex w-full min-w-0 flex-col gap-2 px-3.5 py-3 text-left outline-none"
            >
                <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[11px] text-muted">{task.key}</span>
                    <PriorityBadge priority={task.priority} />
                </div>

                <h3
                    className={cn(
                        "line-clamp-2 text-[14px] leading-snug font-semibold break-words",
                        isDone ? "text-muted line-through" : "text-primary",
                    )}
                >
                    <SearchHighlight text={task.search_title ?? task.title} />
                </h3>

                {description && (
                    <p className="line-clamp-2 text-[12px] leading-relaxed text-muted">
                        {task.search_excerpt ? (
                            <SearchHighlight text={task.search_excerpt} />
                        ) : (
                            description
                        )}
                    </p>
                )}

                {task.last_comment && (
                    <p
                        className={cn(
                            "line-clamp-2 rounded-sm border-l-2 border-accent-border/70 bg-white/[0.025]",
                            "px-2 py-1.5 text-[12px] leading-relaxed text-muted",
                        )}
                    >
                        {toPlainText(task.last_comment)}
                    </p>
                )}

                {breadcrumb && (
                    <p className="truncate text-[11px] text-disabled">{breadcrumb}</p>
                )}

                {(task.due_date !== null || task.comments_count > 0 || task.assignee) && (
                    <div className="flex items-center justify-between gap-2 pt-0.5">
                        <DueDate value={task.due_date} isDone={isDone} />
                        <div className="flex items-center gap-2.5 text-[11px] text-muted">
                            {task.assignee && <span className="truncate">{task.assignee}</span>}
                            {task.comments_count > 0 && (
                                <span
                                    className="inline-flex items-center gap-1"
                                    title={`Комментариев: ${task.comments_count}`}
                                >
                                    <MessageSquare size={11} aria-hidden="true" />
                                    {task.comments_count}
                                </span>
                            )}
                        </div>
                    </div>
                )}
            </button>
        </div>
    );
});
