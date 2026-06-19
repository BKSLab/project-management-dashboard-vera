import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { KanbanStage, KanbanTask } from "@/lib/types";
import { StaticTaskCard } from "@/components/kanban/TaskCard";

interface RecentTasksByStageProps {
    stages: KanbanStage[];
    tasks: KanbanTask[];
}

const RECENT_LIMIT = 5;

export function RecentTasksByStage({ stages, tasks }: RecentTasksByStageProps) {
    const navigate = useNavigate();

    const backlogStageId = useMemo(
        () =>
            stages.length > 0
                ? stages.reduce((min, stage) => (stage.order_index < min.order_index ? stage : min)).id
                : null,
        [stages]
    );

    const columns = stages
        .filter((stage) => stage.id !== backlogStageId)
        .map((stage) => ({
            stage,
            recentTasks: tasks
                .filter((task) => task.stage_id === stage.id)
                .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
                .slice(0, RECENT_LIMIT),
        }));

    return (
        <div className="rounded-2xl border border-white/[0.05] bg-surface p-6">
            <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xs font-bold uppercase tracking-widest text-muted">
                    Последние задачи по стадиям
                </h2>
                <Link to="/kanban" className="text-xs text-accent hover:underline">
                    Открыть канбан →
                </Link>
            </div>

            <div
                className="grid gap-4"
                style={{ gridTemplateColumns: `repeat(${Math.max(columns.length, 1)}, minmax(0, 1fr))` }}
            >
                {columns.map(({ stage, recentTasks }) => (
                    <div
                        key={stage.id}
                        className="flex flex-col rounded-xl border border-white/[0.05] bg-surface-elevated"
                    >
                        <div
                            className="border-b-2 px-3 py-2"
                            style={{ borderBottomColor: stage.color }}
                        >
                            <span className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground">
                                {stage.name}
                            </span>
                        </div>
                        <div className="flex flex-1 flex-col gap-2 p-2">
                            {recentTasks.length === 0 ? (
                                <p className="px-1 py-2 text-xs text-muted">Нет задач.</p>
                            ) : (
                                recentTasks.map((task) => (
                                    <StaticTaskCard
                                        key={task.id}
                                        task={task}
                                        onClick={() => navigate(`/kanban?highlight=${task.id}`)}
                                    />
                                ))
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
