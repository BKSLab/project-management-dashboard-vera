import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/cn";
import type { DashboardProject, StageBreakdown as StageBreakdownItem } from "@/lib/types";
import { SegmentedProgress } from "@/components/ui/Progress";
import { StatusDot } from "@/components/ui/Badge";

/**
 * Разрез портфеля: активные проекты, по которым и идёт разбор.
 *
 * Строка отвечает на вопрос «о чём вообще этот вывод»: в разбор попадают
 * только проекты в работе, и они же перечислены здесь со своими цифрами.
 * Проект вне работы показан отдельной подписью — молча пропасть он не
 * должен, иначе непонятно, почему его нет в выводе.
 */
export function PortfolioBreakdown({ projects }: { projects: DashboardProject[] }) {
    const active = projects.filter((project) => project.status === "ACTIVE");
    const resting = projects.length - active.length;

    if (active.length === 0) {
        return (
            <p className="text-[12px] text-muted">
                Активных проектов нет — разбирать нечего. Переведите проект в статус «В работе».
            </p>
        );
    }

    return (
        <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-3">
                <h3 className="text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
                    В разборе
                </h3>
                <span className="font-mono text-[11px] text-disabled">
                    {active.length} из {projects.length}
                </span>
            </div>
            <ul className="scrollbar-thin flex gap-2 overflow-x-auto pb-0.5">
                {active.map((project) => (
                    <li key={project.id} className="shrink-0">
                        <Link
                            to={`/projects/${project.key}`}
                            className={cn(
                                "flex items-center gap-2 rounded-[var(--radius-control)] border",
                                "border-line-subtle bg-surface/60 px-2.5 py-1.5",
                                "transition-colors duration-[var(--duration-fast)] hover:bg-hover",
                            )}
                        >
                            <StatusDot color={project.color} />
                            <span className="font-mono text-[11px] text-secondary">
                                {project.key}
                            </span>
                            <span className="font-mono text-[11px] text-muted">
                                {project.done_tasks}/{project.total_tasks}
                            </span>
                            {project.overdue_tasks > 0 && (
                                <span className="inline-flex items-center gap-1 font-mono text-[11px] text-danger">
                                    <AlertTriangle size={11} aria-hidden="true" />
                                    {project.overdue_tasks}
                                </span>
                            )}
                        </Link>
                    </li>
                ))}
            </ul>
            {resting > 0 && (
                <p className="text-[11px] text-disabled">
                    Вне разбора: {resting} — проекты не в статусе «В работе».
                </p>
            )}
        </div>
    );
}

/**
 * Разрез проекта: сколько задач в каждой стадии.
 *
 * Для проекта единица разбора — задача, поэтому и разрез задачный: полоса
 * стадий показывает, где именно стоит работа, о которой говорит вывод.
 */
export function StageBreakdown({ stages }: { stages: StageBreakdownItem[] }) {
    if (stages.length === 0) {
        return null;
    }

    return (
        <div className="flex flex-col gap-2.5">
            <h3 className="text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
                По стадиям
            </h3>
            <SegmentedProgress
                segments={stages.map((item) => ({
                    id: item.stage_id,
                    value: item.tasks_count,
                    color: item.color,
                    label: item.stage_name,
                }))}
            />
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                {stages.map((item) => (
                    <span
                        key={item.stage_id}
                        className="inline-flex items-center gap-1.5 text-[12px] text-muted"
                    >
                        <StatusDot color={item.color} />
                        {item.stage_name}
                        <span className="font-mono text-secondary">{item.tasks_count}</span>
                    </span>
                ))}
            </div>
        </div>
    );
}
