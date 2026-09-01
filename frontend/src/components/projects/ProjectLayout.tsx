import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { ProjectStats } from "@/lib/types";
import { cn } from "@/lib/cn";
import { useProjectFromRoute } from "@/lib/useProject";
import { ProjectStatusBadge, StatusDot } from "@/components/ui/Badge";
import { IconButton } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/Progress";
import { EmptyState, ErrorMessage, Skeleton } from "@/components/ui/States";
import { TaskDrawer } from "@/components/tasks/TaskDrawer";

const TABS = [
    { path: "", label: "Обзор", end: true },
    { path: "board", label: "Канбан", end: false },
    { path: "tasks", label: "Задачи", end: false },
    { path: "structure", label: "Структура", end: false },
    { path: "docs", label: "Документы", end: false },
];

/**
 * Рабочее пространство проекта: шапка с показателями и вкладки разделов
 * (раздел 5 дизайн-гайда). Содержимое вкладки рендерится через Outlet.
 */
export function ProjectLayout() {
    const { project, projectKey, isPending, error, isMissing } = useProjectFromRoute();

    const statsQuery = useQuery({
        queryKey: queryKeys.projectStats(project?.id ?? 0),
        queryFn: () => api.get<ProjectStats>(endpoints.projectStats(project?.id as number)),
        enabled: project !== undefined,
    });

    if (isPending) {
        return (
            <div className="flex flex-col gap-4 p-5">
                <Skeleton className="h-16 w-full max-w-2xl" />
                <Skeleton className="h-8 w-80" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-5">
                <ErrorMessage message={(error as Error).message} />
            </div>
        );
    }

    if (isMissing || project === undefined) {
        return (
            <div className="p-5">
                <EmptyState
                    title={`Проект ${projectKey} не найден`}
                    description="Возможно, он был удалён или в адресе опечатка."
                />
            </div>
        );
    }

    const percent = Math.round((statsQuery.data?.completion_rate ?? 0) * 100);

    return (
        <div className="flex h-full min-w-0 flex-col">
            <header className="shrink-0 border-b border-line bg-surface px-5 pt-4">
                <div className="mx-auto flex w-full max-w-6xl flex-col gap-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-2.5">
                            {project.icon ? (
                                <span aria-hidden="true" className="mt-0.5 text-lg leading-none">
                                    {project.icon}
                                </span>
                            ) : (
                                <StatusDot color={project.color} className="mt-2.5 size-2" />
                            )}
                            <div className="flex min-w-0 flex-col gap-1">
                                <div className="flex flex-wrap items-center gap-2">
                                    <h1 className="truncate text-lg font-semibold text-primary">
                                        {project.name}
                                    </h1>
                                    <span className="font-mono text-[11px] text-muted">
                                        {project.key}
                                    </span>
                                    <ProjectStatusBadge status={project.status} />
                                </div>
                                {statsQuery.data && (
                                    <p className="text-[12px] text-muted">
                                        {statsQuery.data.total_tasks} задач ·{" "}
                                        {statsQuery.data.in_progress_tasks} в работе ·{" "}
                                        {statsQuery.data.done_tasks} готово
                                        {statsQuery.data.overdue_tasks > 0 && (
                                            <span className="ml-1 text-danger">
                                                · {statsQuery.data.overdue_tasks} просрочено
                                            </span>
                                        )}
                                    </p>
                                )}
                            </div>
                        </div>

                        <div className="flex items-center gap-3">
                            <div className="hidden w-44 items-center gap-2 sm:flex">
                                <ProgressBar
                                    value={statsQuery.data?.completion_rate ?? 0}
                                    color={project.color}
                                    label={`Прогресс проекта ${project.name}`}
                                />
                                <span className="shrink-0 font-mono text-[11px] text-secondary">
                                    {percent}%
                                </span>
                            </div>
                            <NavLink to={`/projects/${project.key}/settings`}>
                                {({ isActive }) => (
                                    <IconButton
                                        label="Настройки проекта"
                                        className={cn(isActive && "bg-accent-soft text-accent")}
                                    >
                                        <Settings size={15} aria-hidden="true" />
                                    </IconButton>
                                )}
                            </NavLink>
                        </div>
                    </div>

                    <nav aria-label="Разделы проекта" className="-mb-px flex gap-1 overflow-x-auto">
                        {TABS.map((tab) => (
                            <NavLink
                                key={tab.path}
                                to={`/projects/${project.key}${tab.path ? `/${tab.path}` : ""}`}
                                end={tab.end}
                                className={({ isActive }) =>
                                    cn(
                                        "border-b-2 px-3 py-2 text-[13px] whitespace-nowrap",
                                        "transition-colors duration-[var(--duration-fast)]",
                                        isActive
                                            ? "border-accent text-primary"
                                            : "border-transparent text-muted hover:text-secondary",
                                    )
                                }
                            >
                                {tab.label}
                            </NavLink>
                        ))}
                    </nav>
                </div>
            </header>

            <div className="min-h-0 flex-1">
                <Outlet context={{ project }} />
            </div>

            <TaskDrawer />
        </div>
    );
}
