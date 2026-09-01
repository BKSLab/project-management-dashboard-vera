import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FolderKanban, ListTodo, Plus } from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { Dashboard } from "@/lib/types";
import { Page } from "@/components/layout/AppShell";
import { LinkButton } from "@/components/ui/Button";
import { Card, Section } from "@/components/ui/Card";
import { StatTile } from "@/components/ui/Progress";
import { EmptyState, ErrorMessage, Skeleton } from "@/components/ui/States";
import { ProjectCard } from "@/components/dashboard/ProjectCard";
import { TaskRow } from "@/components/dashboard/TaskRow";
import { TaskDrawer } from "@/components/tasks/TaskDrawer";
import { useUiStore } from "@/stores/ui";

function DashboardSkeleton() {
    return (
        <div role="status" aria-label="Загрузка сводки" className="flex flex-col gap-6">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {[0, 1, 2, 3].map((index) => (
                    <Skeleton key={index} className="h-[74px]" />
                ))}
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {[0, 1, 2].map((index) => (
                    <Skeleton key={index} className="h-40" />
                ))}
            </div>
        </div>
    );
}

export function DashboardPage() {
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);

    const dashboardQuery = useQuery({
        queryKey: queryKeys.dashboard,
        queryFn: () => api.get<Dashboard>(endpoints.dashboard()),
    });

    return (
        <Page>
            <header className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-col gap-0.5">
                    <h1 className="text-lg font-semibold text-primary">Дашборд</h1>
                    <p className="text-[13px] text-muted">Что происходит со всеми проектами сейчас</p>
                </div>
                <LinkButton to="/projects/new" variant="primary" icon={<Plus size={15} />}>
                    Новый проект
                </LinkButton>
            </header>

            {dashboardQuery.isPending && <DashboardSkeleton />}
            {dashboardQuery.error && (
                <ErrorMessage message={(dashboardQuery.error as Error).message} />
            )}

            {dashboardQuery.data && (
                <>
                    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                        <StatTile
                            label="Активные проекты"
                            value={dashboardQuery.data.totals.active_projects}
                            hint={`Всего проектов: ${dashboardQuery.data.totals.total_projects}`}
                            icon={<FolderKanban size={12} />}
                        />
                        <StatTile
                            label="Задачи в работе"
                            value={dashboardQuery.data.totals.in_progress_tasks}
                            hint={`Всего задач: ${dashboardQuery.data.totals.total_tasks}`}
                            icon={<ListTodo size={12} />}
                        />
                        <StatTile
                            label="Выполнено"
                            value={`${Math.round(dashboardQuery.data.totals.completion_rate * 100)}%`}
                            hint={`${dashboardQuery.data.totals.done_tasks} задач закрыто`}
                            tone="success"
                            icon={<CheckCircle2 size={12} />}
                        />
                        <StatTile
                            label="Просрочено"
                            value={dashboardQuery.data.totals.overdue_tasks}
                            hint={
                                dashboardQuery.data.totals.overdue_tasks > 0
                                    ? "Требует внимания"
                                    : "Всё в срок"
                            }
                            tone={
                                dashboardQuery.data.totals.overdue_tasks > 0 ? "danger" : "default"
                            }
                            icon={<AlertTriangle size={12} />}
                        />
                    </div>

                    <Section
                        title="Проекты"
                        action={
                            <Link
                                to="/projects"
                                className="text-[13px] text-accent hover:text-accent-hover"
                            >
                                Все проекты
                            </Link>
                        }
                    >
                        {dashboardQuery.data.projects.length === 0 ? (
                            <EmptyState
                                title="Проектов пока нет"
                                description="Создайте первый проект, чтобы начать вести задачи и структуру работ."
                                icon={<FolderKanban size={24} />}
                                action={
                                    <LinkButton
                                        to="/projects/new"
                                        variant="primary"
                                        icon={<Plus size={15} />}
                                    >
                                        Создать проект
                                    </LinkButton>
                                }
                            />
                        ) : (
                            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                                {dashboardQuery.data.projects.map((project) => (
                                    <ProjectCard key={project.id} project={project} />
                                ))}
                            </div>
                        )}
                    </Section>

                    <div className="grid gap-6 xl:grid-cols-2">
                        <Section title="Требуют внимания">
                            <Card className="p-1.5">
                                {dashboardQuery.data.attention_tasks.length === 0 ? (
                                    <p className="px-2.5 py-6 text-center text-[13px] text-muted">
                                        Просроченных и ближайших сроков нет.
                                    </p>
                                ) : (
                                    dashboardQuery.data.attention_tasks.map((task) => (
                                        <TaskRow
                                            key={task.id}
                                            task={task}
                                            onOpen={setSelectedTaskId}
                                        />
                                    ))
                                )}
                            </Card>
                        </Section>

                        <Section title="Недавно изменённые">
                            <Card className="p-1.5">
                                {dashboardQuery.data.recent_tasks.length === 0 ? (
                                    <p className="px-2.5 py-6 text-center text-[13px] text-muted">
                                        Изменений пока не было.
                                    </p>
                                ) : (
                                    dashboardQuery.data.recent_tasks.map((task) => (
                                        <TaskRow
                                            key={task.id}
                                            task={task}
                                            showUpdated
                                            onOpen={setSelectedTaskId}
                                        />
                                    ))
                                )}
                            </Card>
                        </Section>
                    </div>
                </>
            )}

            <TaskDrawer />
        </Page>
    );
}
