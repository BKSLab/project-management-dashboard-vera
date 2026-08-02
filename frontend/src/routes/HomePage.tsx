import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DocumentListItem, KanbanStage, KanbanTask, WbsNode } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Spinner } from "@/components/ui/Spinner";
import { KanbanPulse } from "@/components/dashboard/KanbanPulse";
import { RecentTasksByStage } from "@/components/dashboard/RecentTasksByStage";
import { BacklogPreview } from "@/components/dashboard/BacklogPreview";

function sumProgress(nodes: WbsNode[]): { done: number; total: number } {
    let done = 0;
    let total = 0;
    for (const node of nodes) {
        if (node.progress) {
            done += node.progress.done;
            total += node.progress.total;
        }
    }
    return { done, total };
}

export function HomePage() {
    const documentsQuery = useQuery({
        queryKey: ["documents"],
        queryFn: () => api.get<DocumentListItem[]>("/api/v1/documents"),
    });

    const wbsQuery = useQuery({
        queryKey: ["wbs", "tree"],
        queryFn: () => api.get<WbsNode[]>("/api/v1/wbs/tree"),
    });

    const stagesQuery = useQuery({
        queryKey: ["kanban", "stages"],
        queryFn: () => api.get<KanbanStage[]>("/api/v1/kanban/stages"),
    });

    const tasksQuery = useQuery({
        queryKey: ["kanban", "tasks"],
        queryFn: () => api.get<KanbanTask[]>("/api/v1/kanban/tasks"),
    });

    const progress = wbsQuery.data ? sumProgress(wbsQuery.data) : null;
    const percent = progress && progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;

    const doneStageIds = useMemo(
        () => new Set((stagesQuery.data ?? []).filter((stage) => stage.is_done_stage).map((stage) => stage.id)),
        [stagesQuery.data]
    );

    const upcomingDeadlines = useMemo(() => {
        if (!tasksQuery.data) return [];
        return tasksQuery.data
            .filter((task) => task.due_date && !doneStageIds.has(task.stage_id))
            .sort((a, b) => (a.due_date! < b.due_date! ? -1 : 1))
            .slice(0, 5);
    }, [tasksQuery.data, doneStageIds]);

    const isPending =
        documentsQuery.isPending || wbsQuery.isPending || tasksQuery.isPending || stagesQuery.isPending;

    return (
        <div className="mx-auto max-w-[1440px]">
            <FocusHeading className="mb-6 text-3xl font-bold">
                Дашборд «Агент Вера»
            </FocusHeading>

            {isPending && <Spinner />}

            {!isPending && (
                <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-lg border border-white/20 bg-surface p-6">
                        <p className="text-xs uppercase tracking-wider text-muted">Готовность ИСР</p>
                        <p className="mt-2 text-3xl font-bold text-accent">{percent}%</p>
                        <p className="mt-1 text-xs text-muted">
                            {progress?.done ?? 0} из {progress?.total ?? 0} задач
                        </p>
                        <Link to="/wbs" className="mt-3 inline-block text-sm text-accent hover:underline">
                            Открыть ИСР →
                        </Link>
                    </div>

                    <div className="rounded-lg border border-white/20 bg-surface p-6">
                        <p className="text-xs uppercase tracking-wider text-muted">Документы</p>
                        <p className="mt-2 text-3xl font-bold text-foreground">
                            {documentsQuery.data?.length ?? 0}
                        </p>
                        <Link to="/docs" className="mt-3 inline-block text-sm text-accent hover:underline">
                            К документам →
                        </Link>
                    </div>

                    <div className="rounded-lg border border-white/20 bg-surface p-6">
                        <p className="mb-2 text-xs uppercase tracking-wider text-muted">Ближайшие сроки</p>
                        {upcomingDeadlines.length === 0 ? (
                            <p className="text-sm text-muted">Нет задач со сроком.</p>
                        ) : (
                            <ul className="space-y-1">
                                {upcomingDeadlines.map((task) => (
                                    <li key={task.id} className="flex items-center justify-between gap-2 text-sm">
                                        <span className="truncate text-foreground">{task.title}</span>
                                        <span className="shrink-0 text-xs text-muted">
                                            {new Date(task.due_date!).toLocaleDateString("ru-RU")}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        )}
                        <Link to="/kanban" className="mt-3 inline-block text-sm text-accent hover:underline">
                            К канбану →
                        </Link>
                    </div>
                </div>
            )}

            {!isPending && stagesQuery.data && tasksQuery.data && (
                <div className="mt-6">
                    <KanbanPulse stages={stagesQuery.data} tasks={tasksQuery.data} />
                </div>
            )}

            {!isPending && stagesQuery.data && tasksQuery.data && (
                <div className="mt-6">
                    <RecentTasksByStage stages={stagesQuery.data} tasks={tasksQuery.data} />
                </div>
            )}

            {!isPending && stagesQuery.data && tasksQuery.data && (
                <div className="mt-6">
                    <BacklogPreview stages={stagesQuery.data} tasks={tasksQuery.data} />
                </div>
            )}
        </div>
    );
}
