import { useDroppable } from "@dnd-kit/core";
import { Flag } from "lucide-react";
import { calendarDateDropId, type CalendarDayModel } from "@/lib/calendar";
import { cn } from "@/lib/cn";
import type { CalendarStage, CalendarTask as CalendarTaskModel } from "@/lib/types";
import { CalendarTask } from "@/components/calendar/CalendarTask";

const MAX_VISIBLE_TASKS = 3;

interface CalendarDayProps {
    day: CalendarDayModel;
    tasks: CalendarTaskModel[];
    stagesById: Map<number, CalendarStage>;
    projectDueDate: string | null;
    selected: boolean;
    onSelect: (date: string) => void;
    onOpenTask: (taskId: number) => void;
}

export function CalendarDay({
    day,
    tasks,
    stagesById,
    projectDueDate,
    selected,
    onSelect,
    onOpenTask,
}: CalendarDayProps) {
    const { isOver, setNodeRef } = useDroppable({ id: calendarDateDropId(day.date) });
    const hiddenCount = Math.max(tasks.length - MAX_VISIBLE_TASKS, 0);
    const isProjectDeadline = day.date === projectDueDate;

    return (
        <section
            ref={setNodeRef}
            aria-label={day.date}
            className={cn(
                "relative flex min-h-28 min-w-0 flex-col gap-1 border-r border-b border-line-subtle p-1.5",
                day.isWeekend && "bg-surface-2/35",
                !day.inCurrentMonth && "bg-app/35 opacity-55",
                selected && "z-10 ring-1 ring-inset ring-accent-border",
                isOver && "z-20 bg-accent/10 ring-2 ring-inset ring-accent",
            )}
        >
            {day.isToday && (
                <span aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-accent" />
            )}
            <button
                type="button"
                onClick={() => onSelect(day.date)}
                aria-label={`Открыть agenda за ${day.date}`}
                className={cn(
                    "flex h-6 w-6 items-center justify-center self-end rounded-full text-[11px]",
                    day.isToday
                        ? "bg-accent font-semibold text-app"
                        : "text-muted hover:bg-hover hover:text-primary",
                )}
            >
                {day.dayNumber}
            </button>
            {isProjectDeadline && (
                <div
                    className="flex items-center gap-1 rounded-sm border border-purple/35 bg-purple/10 px-1 py-0.5 text-[10px] text-purple"
                    title="Плановый дедлайн проекта"
                >
                    <Flag size={10} aria-hidden="true" />
                    <span className="truncate">Дедлайн проекта</span>
                </div>
            )}
            <div className="flex min-w-0 flex-col gap-1">
                {tasks.slice(0, MAX_VISIBLE_TASKS).map((task) => (
                    <CalendarTask
                        key={task.id}
                        task={task}
                        stageName={stagesById.get(task.stage_id)?.name}
                        compact
                        draggable
                        onOpen={onOpenTask}
                    />
                ))}
            </div>
            {hiddenCount > 0 && (
                <button
                    type="button"
                    onClick={() => onSelect(day.date)}
                    className="mt-auto self-start px-1 text-[10px] text-muted hover:text-accent"
                >
                    +{hiddenCount} в agenda
                </button>
            )}
        </section>
    );
}
