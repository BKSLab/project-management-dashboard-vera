import { Link } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { KanbanStage, KanbanTask } from "@/lib/types";

interface KanbanPulseProps {
    stages: KanbanStage[];
    tasks: KanbanTask[];
}

function localDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

export function KanbanPulse({ stages, tasks }: KanbanPulseProps) {
    const orderedStages = [...stages].sort((a, b) => a.order_index - b.order_index);
    const countsByStage = new Map<number, number>();
    for (const task of tasks) {
        countsByStage.set(task.stage_id, (countsByStage.get(task.stage_id) ?? 0) + 1);
    }

    const counts = orderedStages.map((stage) => ({
        stage,
        count: countsByStage.get(stage.id) ?? 0,
    }));
    const total = tasks.length;
    const doneStageIds = new Set(
        orderedStages.filter((stage) => stage.is_done_stage).map((stage) => stage.id)
    );
    const doneCount = tasks.filter((task) => doneStageIds.has(task.stage_id)).length;
    const donePercent = total > 0 ? Math.round((doneCount / total) * 100) : 0;

    const today = localDateKey(new Date());
    const overdueCount = tasks.filter(
        (task) => task.due_date && task.due_date < today && !doneStageIds.has(task.stage_id)
    ).length;

    const pieData = counts
        .filter(({ count }) => count > 0)
        .map(({ stage, count }) => ({
            name: stage.name,
            value: count,
            color: stage.color,
        }));

    return (
        <section className="rounded-2xl border border-white/20 bg-surface p-5 sm:p-6">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h2 className="text-xs font-bold uppercase tracking-widest text-muted">
                        Пульс канбана
                    </h2>
                    <p className="mt-1 text-sm text-foreground">Распределение задач по стадиям</p>
                </div>
                <div className="flex items-center gap-3">
                    {overdueCount > 0 && (
                        <span className="rounded-full bg-danger/10 px-2.5 py-1 text-xs font-semibold text-danger ring-1 ring-inset ring-danger/25">
                            {overdueCount} просрочено
                        </span>
                    )}
                    <Link to="/kanban" className="text-xs text-accent hover:underline">
                        Открыть канбан →
                    </Link>
                </div>
            </div>

            {total === 0 ? (
                <p className="py-10 text-center text-sm text-muted">Нет задач.</p>
            ) : (
                <div className="flex flex-col gap-7 lg:flex-row lg:items-center lg:gap-10">
                    <div className="flex shrink-0 items-center justify-center gap-5 lg:block">
                        <div className="relative h-40 w-40 shrink-0">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={pieData}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={48}
                                        outerRadius={70}
                                        paddingAngle={2}
                                        dataKey="value"
                                        strokeWidth={0}
                                        isAnimationActive={false}
                                    >
                                        {pieData.map((entry) => (
                                            <Cell key={entry.name} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={{
                                            background: "var(--surface)",
                                            border: "1px solid var(--border)",
                                            borderRadius: "8px",
                                            fontSize: "12px",
                                            color: "var(--foreground)",
                                        }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                                <div className="text-center">
                                    <div className="text-2xl font-bold text-foreground">{total}</div>
                                    <div className="text-[10px] text-muted">всего задач</div>
                                </div>
                            </div>
                        </div>
                        <div className="text-center lg:mt-1">
                            <p className="text-lg font-bold text-success">{donePercent}%</p>
                            <p className="text-xs text-muted">завершено</p>
                        </div>
                    </div>

                    <div className="min-w-0 flex-1 space-y-3.5">
                        {counts.map(({ stage, count }) => {
                            const percent = Math.round((count / total) * 100);

                            return (
                                <div key={stage.id} className="grid grid-cols-[minmax(7rem,9rem)_1fr_auto] items-center gap-3">
                                    <div className="flex min-w-0 items-center gap-2">
                                        <span
                                            className="h-2.5 w-2.5 shrink-0 rounded-full"
                                            style={{ backgroundColor: stage.color }}
                                        />
                                        <span className="truncate text-xs text-muted" title={stage.name}>
                                            {stage.name}
                                        </span>
                                    </div>
                                    <div
                                        role="progressbar"
                                        aria-label={`${stage.name}: ${count} из ${total} задач`}
                                        aria-valuemin={0}
                                        aria-valuemax={total}
                                        aria-valuenow={count}
                                        className="h-2.5 overflow-hidden rounded-full bg-border"
                                    >
                                        <div
                                            className="h-full min-w-px rounded-full transition-[width] duration-500"
                                            style={{
                                                width: count > 0 ? `${Math.max(percent, 1)}%` : "0%",
                                                backgroundColor: stage.color,
                                            }}
                                        />
                                    </div>
                                    <div className="flex w-20 shrink-0 items-baseline justify-end gap-2">
                                        <span className="text-sm font-bold text-foreground">{count}</span>
                                        <span className="w-9 text-right font-mono text-[11px] text-muted">
                                            {percent}%
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </section>
    );
}
