import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import type { TaskPriority } from "@/lib/types";
import { PriorityBadge, StatusDot } from "@/components/ui/Badge";

interface TaskLineProps {
    /** Цвет проекта: нужен там, где в списке смешаны разные проекты. */
    dotColor?: string;
    taskKey: string;
    title: string;
    stage?: string | null;
    priority?: TaskPriority | null;
    /** Правая колонка: срок, время изменения или другой одиночный факт. */
    meta?: ReactNode;
    onOpen: () => void;
}

/**
 * Строка задачи в любом списке приложения.
 *
 * Колонки фиксированной ширины: два списка рядом должны читаться как одна
 * таблица, а не как два по-разному сжатых столбца. Ключ, стадия, приоритет
 * и правый факт стоят на одних и тех же позициях, поэтому взгляд идёт
 * сверху вниз по колонке, а не ищет её заново в каждой строке.
 */
export function TaskLine({
    dotColor,
    taskKey,
    title,
    stage,
    priority,
    meta,
    onOpen,
}: TaskLineProps) {
    return (
        <button
            type="button"
            onClick={onOpen}
            className={cn(
                "flex w-full min-w-0 items-center gap-3 rounded-md px-2.5 py-2 text-left",
                "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
                "hover:bg-hover",
            )}
        >
            {dotColor ? <StatusDot color={dotColor} /> : null}
            <span className="w-20 shrink-0 truncate font-mono text-[11px] text-muted">
                {taskKey}
            </span>
            <span className="min-w-0 flex-1 truncate text-[13px] text-secondary">{title}</span>
            <span className="hidden w-24 shrink-0 truncate text-right text-[11px] text-muted sm:inline">
                {stage ?? ""}
            </span>
            <span className="hidden w-[5.5rem] shrink-0 justify-end sm:flex">
                {priority ? <PriorityBadge priority={priority} /> : null}
            </span>
            <span className="w-24 shrink-0 text-right text-[11px] text-muted">{meta}</span>
        </button>
    );
}
