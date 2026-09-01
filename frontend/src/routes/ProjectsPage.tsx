import { useQuery } from "@tanstack/react-query";
import { FolderKanban, Plus } from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { Dashboard } from "@/lib/types";
import { Page } from "@/components/layout/AppShell";
import { LinkButton } from "@/components/ui/Button";
import { EmptyState, ErrorMessage, Skeleton } from "@/components/ui/States";
import { ProjectCard } from "@/components/dashboard/ProjectCard";

export function ProjectsPage() {
    const dashboardQuery = useQuery({
        queryKey: queryKeys.dashboard,
        queryFn: () => api.get<Dashboard>(endpoints.dashboard()),
    });

    return (
        <Page>
            <header className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-col gap-0.5">
                    <h1 className="text-lg font-semibold text-primary">Проекты</h1>
                    <p className="text-[13px] text-muted">
                        {dashboardQuery.data
                            ? `${dashboardQuery.data.totals.total_projects} проектов, ${dashboardQuery.data.totals.total_tasks} задач`
                            : "Все проекты трекера"}
                    </p>
                </div>
                <LinkButton to="/projects/new" variant="primary" icon={<Plus size={15} />}>
                    Новый проект
                </LinkButton>
            </header>

            {dashboardQuery.isPending && (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {[0, 1, 2, 3, 4, 5].map((index) => (
                        <Skeleton key={index} className="h-40" />
                    ))}
                </div>
            )}

            {dashboardQuery.error && (
                <ErrorMessage message={(dashboardQuery.error as Error).message} />
            )}

            {dashboardQuery.data &&
                (dashboardQuery.data.projects.length === 0 ? (
                    <EmptyState
                        title="Проектов пока нет"
                        description="Создайте первый проект, чтобы вести задачи, структуру работ и документы."
                        icon={<FolderKanban size={24} />}
                        action={
                            <LinkButton to="/projects/new" variant="primary" icon={<Plus size={15} />}>
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
                ))}
        </Page>
    );
}
