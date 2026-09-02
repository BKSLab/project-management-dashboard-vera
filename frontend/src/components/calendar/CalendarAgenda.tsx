import { CalendarX2, Inbox } from "lucide-react";
import { dayTitle } from "@/lib/calendar";
import type { CalendarStage, CalendarTask as CalendarTaskModel } from "@/lib/types";
import { CalendarTask } from "@/components/calendar/CalendarTask";
import { Button } from "@/components/ui/Button";

interface CalendarAgendaProps {
    selectedDate: string;
    tasks: CalendarTaskModel[];
    unscheduledTasks: CalendarTaskModel[];
    stagesById: Map<number, CalendarStage>;
    hasMoreUnscheduled: boolean;
    isLoadingMore: boolean;
    onOpenTask: (taskId: number) => void;
    onScheduleTask: (task: CalendarTaskModel) => void;
    onLoadMore: () => void;
}

export function CalendarAgenda({
    selectedDate,
    tasks,
    unscheduledTasks,
    stagesById,
    hasMoreUnscheduled,
    isLoadingMore,
    onOpenTask,
    onScheduleTask,
    onLoadMore,
}: CalendarAgendaProps) {
    return (
        <div className="flex flex-col gap-3">
            <section className="rounded-lg border border-line bg-surface p-3 shadow-card">
                <h3 className="mb-2 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
                    {dayTitle(selectedDate)}
                </h3>
                {tasks.length === 0 ? (
                    <div className="flex items-center gap-2 py-2 text-[12px] text-muted">
                        <CalendarX2 size={14} aria-hidden="true" />
                        На этот день плановых задач нет
                    </div>
                ) : (
                    <div className="flex flex-col gap-1.5">
                        {tasks.map((task) => (
                            <CalendarTask
                                key={task.id}
                                task={task}
                                stageName={stagesById.get(task.stage_id)?.name}
                                draggable
                                onOpen={onOpenTask}
                                onSchedule={onScheduleTask}
                            />
                        ))}
                    </div>
                )}
            </section>

            <section className="rounded-lg border border-line bg-surface p-3 shadow-card">
                <div className="mb-2 flex items-center gap-2">
                    <Inbox size={14} className="text-muted" aria-hidden="true" />
                    <h3 className="text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
                        Без срока
                    </h3>
                    <span className="ml-auto font-mono text-[11px] text-disabled">
                        {unscheduledTasks.length}
                    </span>
                </div>
                {unscheduledTasks.length === 0 ? (
                    <p className="py-2 text-[12px] text-muted">Все видимые задачи запланированы.</p>
                ) : (
                    <div className="flex max-h-64 flex-col gap-1.5 overflow-y-auto pr-1">
                        {unscheduledTasks.map((task) => (
                            <CalendarTask
                                key={task.id}
                                task={task}
                                stageName={stagesById.get(task.stage_id)?.name}
                                draggable
                                onOpen={onOpenTask}
                                onSchedule={onScheduleTask}
                            />
                        ))}
                    </div>
                )}
                {hasMoreUnscheduled && (
                    <Button
                        size="sm"
                        variant="ghost"
                        className="mt-2 w-full"
                        disabled={isLoadingMore}
                        onClick={onLoadMore}
                    >
                        {isLoadingMore ? "Загрузка…" : "Показать ещё"}
                    </Button>
                )}
            </section>
        </div>
    );
}
