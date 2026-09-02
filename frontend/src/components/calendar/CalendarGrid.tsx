import type { CalendarDayModel } from "@/lib/calendar";
import type { CalendarStage, CalendarTask } from "@/lib/types";
import { CalendarDay } from "@/components/calendar/CalendarDay";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

interface CalendarGridProps {
    days: CalendarDayModel[];
    groupedTasks: Map<string, CalendarTask[]>;
    stagesById: Map<number, CalendarStage>;
    projectDueDate: string | null;
    selectedDate: string;
    onSelectDate: (date: string) => void;
    onOpenTask: (taskId: number) => void;
}

export function CalendarGrid({
    days,
    groupedTasks,
    stagesById,
    projectDueDate,
    selectedDate,
    onSelectDate,
    onOpenTask,
}: CalendarGridProps) {
    return (
        <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
            <div className="grid grid-cols-7 border-b border-line bg-surface-2">
                {WEEKDAYS.map((weekday, index) => (
                    <div
                        key={weekday}
                        className="border-r border-line-subtle px-2 py-1.5 text-center text-[10px] font-semibold tracking-[0.08em] text-muted uppercase last:border-r-0"
                    >
                        {weekday}
                        {index >= 5 && <span className="sr-only">, выходной</span>}
                    </div>
                ))}
            </div>
            <div className="grid grid-cols-7" role="grid" aria-label="Календарь проекта">
                {days.map((day) => (
                    <CalendarDay
                        key={day.date}
                        day={day}
                        tasks={groupedTasks.get(day.date) ?? []}
                        stagesById={stagesById}
                        projectDueDate={projectDueDate}
                        selected={selectedDate === day.date}
                        onSelect={onSelectDate}
                        onOpenTask={onOpenTask}
                    />
                ))}
            </div>
        </div>
    );
}
