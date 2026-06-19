import { Link } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { KanbanStage, KanbanTask } from "@/lib/types";

interface KanbanPulseProps {
    stages: KanbanStage[];
    tasks: KanbanTask[];
}

export function KanbanPulse({ stages, tasks }: KanbanPulseProps) {
    const counts = stages.map((stage) => ({
        stage,
        count: tasks.filter((task) => task.stage_id === stage.id).length,
    }));
    const total = tasks.length;

    const pieData = counts
        .filter(({ count }) => count > 0)
        .map(({ stage, count }) => ({ name: stage.name, value: count, color: stage.color }));

    return (
        <div className="rounded-2xl border border-white/20 bg-surface p-6">
            <div className="mb-5 flex items-center justify-between">
                <h2 className="text-xs font-bold uppercase tracking-widest text-muted">
                    Пульс канбана
                </h2>
                <Link to="/kanban" className="text-xs text-accent hover:underline">
                    Открыть канбан →
                </Link>
            </div>

            {total === 0 ? (
                <p className="py-10 text-center text-sm text-muted">Нет задач.</p>
            ) : (
                <div className="flex flex-wrap items-center gap-8">
                    <div className="relative h-[160px] w-[160px] shrink-0">
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
                                >
                                    {pieData.map((entry, index) => (
                                        <Cell key={index} fill={entry.color} />
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
                                <div className="text-[10px] text-muted">всего</div>
                            </div>
                        </div>
                    </div>

                    <div className="min-w-64 flex-1 space-y-2.5">
                        {counts.map(({ stage, count }) => (
                            <div key={stage.id} className="flex items-center gap-3">
                                <span
                                    className="h-2 w-2 shrink-0 rounded-full"
                                    style={{ backgroundColor: stage.color }}
                                />
                                <span className="w-32 shrink-0 truncate text-xs text-muted">
                                    {stage.name}
                                </span>
                                <div className="h-2 flex-1 overflow-hidden rounded-full bg-border">
                                    <div
                                        className="h-full rounded-full transition-all"
                                        style={{
                                            width: total > 0 ? `${(count / total) * 100}%` : "0%",
                                            backgroundColor: stage.color,
                                        }}
                                    />
                                </div>
                                <span className="w-6 shrink-0 text-right text-sm font-bold text-foreground">
                                    {count}
                                </span>
                                <span className="w-10 shrink-0 text-right text-[11px] font-mono text-muted">
                                    {total > 0 ? `${Math.round((count / total) * 100)}%` : "0%"}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
