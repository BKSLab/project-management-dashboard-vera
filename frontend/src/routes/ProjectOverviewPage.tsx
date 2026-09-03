import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, CheckCircle2, ListTodo, Network } from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { ProjectStats, Task } from "@/lib/types";
import { formatDayMonth } from "@/lib/dates";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { useUiStore } from "@/stores/ui";
import { Card, Section } from "@/components/ui/Card";
import { SegmentedProgress, StatStrip, StatTile } from "@/components/ui/Progress";
import { StatusDot } from "@/components/ui/Badge";
import { DueDate } from "@/components/ui/DueDate";
import { ErrorMessage, Skeleton } from "@/components/ui/States";
import { useRenderedMarkdown } from "@/lib/useRenderedMarkdown";

function Description({ markdown }: { markdown: string }) {
    const html = useRenderedMarkdown(markdown);
    return (
        <div
            className="markdown-body text-[13px]"
            // Содержимое очищается DOMPurify внутри renderMarkdown.
            dangerouslySetInnerHTML={{ __html: html }}
        />
    );
}

export function ProjectOverviewPage() {
    const project = useProjectOutlet();
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);

    const statsQuery = useQuery({
        queryKey: queryKeys.projectStats(project.id),
        queryFn: () => api.get<ProjectStats>(endpoints.projectStats(project.id)),
    });

    const tasksQuery = useQuery({
        queryKey: queryKeys.tasks(project.id),
        queryFn: () => api.get<Task[]>(endpoints.projectTasks(project.id)),
    });

    const stats = statsQuery.data;
    const doneStageIds = new Set(
        (stats?.stage_breakdown ?? []).filter((item) => item.is_done_stage).map((item) => item.stage_id),
    );
    const upcoming = (tasksQuery.data ?? [])
        .filter((task) => task.due_date !== null && !doneStageIds.has(task.stage_id))
        .sort((first, second) => (first.due_date ?? "").localeCompare(second.due_date ?? ""))
        .slice(0, 8);

    return (
        <div className="scrollbar-thin h-full overflow-y-auto">
            <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-5 py-5">
                {statsQuery.error && <ErrorMessage message={(statsQuery.error as Error).message} />}

                {statsQuery.isPending ? (
                    <Skeleton className="h-[88px] w-full" />
                ) : (
                    stats && (
                        <>
                            <StatStrip>
                                <StatTile
                                    label="Всего задач"
                                    value={stats.total_tasks}
                                    hint={`${stats.in_progress_tasks} в работе`}
                                    icon={<ListTodo size={12} />}
                                />
                                <StatTile
                                    label="Выполнено"
                                    value={`${Math.round(stats.completion_rate * 100)}%`}
                                    hint={`${stats.done_tasks} задач закрыто`}
                                    tone="success"
                                    icon={<CheckCircle2 size={12} />}
                                />
                                <StatTile
                                    label="Просрочено"
                                    value={stats.overdue_tasks}
                                    hint={
                                        stats.due_soon_tasks > 0
                                            ? `${stats.due_soon_tasks} со сроком на неделе`
                                            : "Ближайших сроков нет"
                                    }
                                    tone={stats.overdue_tasks > 0 ? "danger" : "default"}
                                    icon={<AlertTriangle size={12} />}
                                />
                                <StatTile
                                    label="Не в структуре"
                                    value={stats.unassigned_tasks}
                                    hint="Задач вне разделов ИСР"
                                    icon={<Network size={12} />}
                                />
                            </StatStrip>

                            <Section title="Распределение по стадиям">
                                <Card className="flex flex-col gap-3 p-4">
                                    <SegmentedProgress
                                        segments={stats.stage_breakdown.map((item) => ({
                                            id: item.stage_id,
                                            value: item.tasks_count,
                                            color: item.color,
                                            label: item.stage_name,
                                        }))}
                                    />
                                    <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                                        {stats.stage_breakdown.map((item) => (
                                            <span
                                                key={item.stage_id}
                                                className="inline-flex items-center gap-1.5 text-[12px] text-muted"
                                            >
                                                <StatusDot color={item.color} />
                                                {item.stage_name}
                                                <span className="font-mono text-secondary">
                                                    {item.tasks_count}
                                                </span>
                                            </span>
                                        ))}
                                    </div>
                                </Card>
                            </Section>
                        </>
                    )
                )}

                <div className="grid gap-6 lg:grid-cols-2">
                    <Section title="Ближайшие сроки">
                        <div className="rounded-[var(--radius-card)] bg-surface/45 p-1.5">
                            {upcoming.length === 0 ? (
                                <p className="px-2.5 py-6 text-center text-[13px] text-muted">
                                    Задач со сроками нет.
                                </p>
                            ) : (
                                upcoming.map((task) => (
                                    <button
                                        key={task.id}
                                        type="button"
                                        onClick={() => setSelectedTaskId(task.id)}
                                        className="flex w-full min-w-0 items-center gap-3 rounded-md px-2.5 py-2 text-left hover:bg-hover"
                                    >
                                        <span className="w-20 shrink-0 truncate font-mono text-[11px] text-muted">
                                            {task.key}
                                        </span>
                                        <span className="min-w-0 flex-1 truncate text-[13px] text-secondary">
                                            {task.title}
                                        </span>
                                        <DueDate value={task.due_date} />
                                    </button>
                                ))
                            )}
                        </div>
                    </Section>

                    <Section title="О проекте">
                        <div className="flex flex-col gap-3 px-1 py-1.5">
                            {project.description_md ? (
                                <Description markdown={project.description_md} />
                            ) : (
                                <p className="text-[13px] text-muted">
                                    Описание проекта пока не заполнено.
                                </p>
                            )}
                            <dl className="flex flex-col gap-1.5 border-t border-line-subtle pt-3 text-[12px]">
                                {project.start_date && (
                                    <div className="flex items-center gap-2">
                                        <dt className="text-muted">Старт:</dt>
                                        <dd className="font-mono text-secondary">
                                            {formatDayMonth(project.start_date)}
                                        </dd>
                                    </div>
                                )}
                                {project.due_date && (
                                    <div className="flex items-center gap-2">
                                        <dt className="text-muted">Плановое завершение:</dt>
                                        <dd className="inline-flex items-center gap-1 font-mono text-secondary">
                                            <CalendarClock size={12} aria-hidden="true" />
                                            {formatDayMonth(project.due_date)}
                                        </dd>
                                    </div>
                                )}
                                {stats?.next_due_date && (
                                    <div className="flex items-center gap-2">
                                        <dt className="text-muted">Ближайший срок задачи:</dt>
                                        <dd className="font-mono text-secondary">
                                            {formatDayMonth(stats.next_due_date)}
                                        </dd>
                                    </div>
                                )}
                            </dl>
                        </div>
                    </Section>
                </div>
            </div>
        </div>
    );
}
