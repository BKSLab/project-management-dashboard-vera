import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import type { DashboardProject } from "@/lib/types";
import { formatDayMonth } from "@/lib/dates";
import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/Progress";
import { ProjectStatusBadge, StatusDot } from "@/components/ui/Badge";

/**
 * Карточка проекта по макету раздела 6: название, краткое описание, прогресс,
 * счётчики и ближайший срок. Красный цвет — только при реальной просрочке.
 */
export function ProjectCard({ project }: { project: DashboardProject }) {
    const percent = Math.round(project.completion_rate * 100);

    return (
        <Card interactive className="min-w-0">
            <Link
                to={`/projects/${project.key}`}
                className="flex min-w-0 flex-col gap-3 p-4 outline-none"
            >
                <div className="flex min-w-0 items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-2.5">
                        {project.icon ? (
                            <span aria-hidden="true" className="mt-0.5 shrink-0 text-base leading-none">
                                {project.icon}
                            </span>
                        ) : (
                            <StatusDot color={project.color} className="mt-2" />
                        )}
                        <div className="flex min-w-0 flex-col gap-0.5">
                            <h3 className="truncate text-[15px] font-semibold text-primary">
                                {project.name}
                            </h3>
                            <span className="font-mono text-[11px] text-muted">{project.key}</span>
                        </div>
                    </div>
                    <ProjectStatusBadge status={project.status} className="shrink-0" />
                </div>

                {project.description_md && (
                    <p className="line-clamp-2 text-[13px] text-muted">{project.description_md}</p>
                )}

                <div className="flex flex-col gap-1.5">
                    <ProgressBar
                        value={project.completion_rate}
                        color={project.color}
                        label={`Прогресс проекта ${project.name}`}
                    />
                    <div className="flex items-center justify-between gap-2 text-[11px]">
                        <span className="text-muted">
                            {project.total_tasks} задач · {project.in_progress_tasks} в работе
                            {project.overdue_tasks > 0 && (
                                <span className="ml-1 inline-flex items-center gap-1 text-danger">
                                    <AlertTriangle size={11} aria-hidden="true" />
                                    {project.overdue_tasks} просрочено
                                </span>
                            )}
                        </span>
                        <span className="font-mono text-secondary">{percent}%</span>
                    </div>
                </div>

                {project.next_due_date && (
                    <p className="text-[11px] text-muted">
                        Ближайший срок:{" "}
                        <span className="font-mono text-secondary">
                            {formatDayMonth(project.next_due_date)}
                        </span>
                    </p>
                )}
            </Link>
        </Card>
    );
}
