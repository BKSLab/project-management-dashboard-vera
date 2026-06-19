import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { KanbanStage, KanbanTask } from "@/lib/types";
import { StaticTaskCard } from "@/components/kanban/TaskCard";
import { compareWbsCode } from "@/lib/sortCode";

interface BacklogPreviewProps {
    stages: KanbanStage[];
    tasks: KanbanTask[];
}

const BACKLOG_LIMIT = 10;

export function BacklogPreview({ stages, tasks }: BacklogPreviewProps) {
    const navigate = useNavigate();

    const backlogStage = useMemo(
        () =>
            stages.length > 0
                ? stages.reduce((min, stage) => (stage.order_index < min.order_index ? stage : min))
                : null,
        [stages]
    );

    const backlogTasks = useMemo(() => {
        if (!backlogStage) return [];
        return tasks
            .filter((task) => task.stage_id === backlogStage.id)
            .sort((a, b) => {
                if (a.wbs_code && b.wbs_code) return compareWbsCode(a.wbs_code, b.wbs_code);
                if (a.wbs_code) return -1;
                if (b.wbs_code) return 1;
                return a.title.localeCompare(b.title, "ru");
            })
            .slice(0, BACKLOG_LIMIT);
    }, [backlogStage, tasks]);

    if (!backlogStage) return null;

    return (
        <div className="rounded-2xl border border-white/[0.05] bg-surface p-6">
            <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xs font-bold uppercase tracking-widest text-muted">
                    {backlogStage.name} · первые {BACKLOG_LIMIT}
                </h2>
                <Link to="/kanban" className="text-xs text-accent hover:underline">
                    Открыть весь бэклог в канбане →
                </Link>
            </div>

            {backlogTasks.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted">Бэклог пуст.</p>
            ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    {backlogTasks.map((task) => (
                        <StaticTaskCard
                            key={task.id}
                            task={task}
                            onClick={() => navigate(`/kanban?highlight=${task.id}`)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
