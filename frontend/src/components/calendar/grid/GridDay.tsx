import type { ReactNode } from "react";
import { CalendarPlus, CalendarX2 } from "lucide-react";
import { dayOffInfo } from "@/lib/calendar";
import { coversDate, taskSpan } from "@/lib/calendarGrid";
import { cn } from "@/lib/cn";
import type { CalendarGridMilestone, CalendarGridTask } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { GridMilestoneChip, GridTaskCard, type GridEnv } from "./GridItems";
import { shortDate, useDayDrop } from "./gridHelpers";

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
    if (count === 0) return null;
    return (
        <section className="flex flex-col gap-1">
            <h4 className="flex items-center gap-2 text-[10px] font-semibold tracking-[0.08em] text-muted uppercase">
                {title} <span className="font-mono">{count}</span>
            </h4>
            {children}
        </section>
    );
}

/**
 * Всё, что приходится на день: сроки, идущие задачи и вехи — списком карточек.
 * Используется в масштабе «День», в «ещё N» и в списке дня на телефоне.
 */
export function DayItemsList({
    date,
    tasks,
    milestones,
    env,
    compact = false,
}: {
    date: string;
    tasks: CalendarGridTask[];
    milestones: CalendarGridMilestone[];
    env: GridEnv;
    compact?: boolean;
}) {
    const dayTasks = tasks.filter((task) => coversDate(task, date));
    const due = dayTasks.filter((task) => (task.due_date ?? task.start_date) === date);
    const ongoing = dayTasks.filter((task) => !due.includes(task));
    const dayMilestones = milestones.filter((milestone) => milestone.due_date === date);
    const variant = compact ? "compact" : "full";
    const off = dayOffInfo(date, env.holidays);

    return (
        <div className="flex flex-col gap-3">
            {compact && (
                <div className="flex items-center justify-between gap-2 px-1">
                    <strong className="text-[12px] text-primary">{shortDate(date)}</strong>
                    <button type="button" className="text-[11px] text-accent hover:underline" onClick={() => env.onOpenPeriod("day", date)}>
                        Открыть день
                    </button>
                </div>
            )}
            {off.title && <p className="px-1 text-[11px] text-muted">{off.title}</p>}
            <Section title="Вехи" count={dayMilestones.length}>
                {dayMilestones.map((milestone) => (
                    <GridMilestoneChip key={`${milestone.id}:${milestone.title}`} milestone={milestone} variant={variant} showProject={env.showSource} />
                ))}
            </Section>
            <Section title="Срок в этот день" count={due.length}>
                {due.map((task) => (
                    <GridTaskCard key={task.id} task={task} date={date} env={env} part={`d:${date}`} variant={variant} />
                ))}
            </Section>
            <Section title="Идут в этот день" count={ongoing.length}>
                {ongoing.map((task) => {
                    const span = taskSpan(task);
                    return (
                        <GridTaskCard
                            key={task.id}
                            task={task}
                            date={date}
                            env={env}
                            part={`o:${date}`}
                            variant={variant}
                            note={span ? `${shortDate(span.start)} — ${shortDate(span.end)}` : undefined}
                        />
                    );
                })}
            </Section>
            {dayTasks.length === 0 && dayMilestones.length === 0 && (
                <p className="px-1 text-[12px] text-muted">
                    {env.onCreate ? "На этот день ничего нет. Создайте задачу или перетащите сюда задачу без срока." : "На этот день ничего не запланировано."}
                </p>
            )}
        </div>
    );
}

/** Масштаб «День»: список карточек без часовой сетки (время у задач не вводится). */
export function GridDay({
    date,
    tasks,
    milestones,
    env,
}: {
    date: string;
    tasks: CalendarGridTask[];
    milestones: CalendarGridMilestone[];
    env: GridEnv;
}) {
    const { setNodeRef, isOver } = useDayDrop(date);
    const isEmpty = !tasks.some((task) => coversDate(task, date)) && !milestones.some((milestone) => milestone.due_date === date);
    return (
        <div
            ref={setNodeRef}
            className={cn("mx-auto flex min-h-full w-full max-w-3xl flex-col gap-4 p-3 sm:p-4", isOver && "bg-accent-soft ring-1 ring-inset ring-accent")}
        >
            {isEmpty ? (
                <div className="flex flex-col items-center gap-3 py-12 text-center">
                    <CalendarX2 size={28} className="text-muted" aria-hidden="true" />
                    <p className="text-[13px] text-secondary">На этот день задач и вех нет.</p>
                    <p className="max-w-sm text-[12px] text-muted">
                        {env.onCreate
                            ? "Создайте задачу со сроком на этот день или перетащите сюда задачу из списка «Без срока»."
                            : "Листайте дни стрелками ← → или откройте неделю/месяц."}
                    </p>
                    {env.onCreate && (
                        <Button size="sm" icon={<CalendarPlus size={13} aria-hidden="true" />} onClick={() => env.onCreate?.(date)}>
                            Новая задача на этот день
                        </Button>
                    )}
                </div>
            ) : (
                <>
                    <DayItemsList date={date} tasks={tasks} milestones={milestones} env={env} />
                    {env.onCreate && (
                        <div>
                            <Button size="sm" variant="ghost" icon={<CalendarPlus size={13} aria-hidden="true" />} onClick={() => env.onCreate?.(date)}>
                                Новая задача на этот день
                            </Button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
