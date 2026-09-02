import { AlertTriangle, CalendarClock, GitCompareArrows, GitMerge, Inbox } from "lucide-react";
import type { CalendarSummary } from "@/lib/types";

export function ProjectPulse({ summary }: { summary: CalendarSummary }) {
    const signals = [
        {
            label: "Просрочено",
            value: summary.overdue,
            icon: <AlertTriangle size={14} aria-hidden="true" />,
            tone: "text-danger",
        },
        {
            label: "Ближайшие 7 дней",
            value: summary.due_soon,
            icon: <CalendarClock size={14} aria-hidden="true" />,
            tone: "text-warning",
        },
        {
            label: "Без срока",
            value: summary.unscheduled,
            icon: <Inbox size={14} aria-hidden="true" />,
            tone: "text-muted",
        },
        {
            label: "Отклонение от baseline",
            value: summary.drifted,
            icon: <GitCompareArrows size={14} aria-hidden="true" />,
            tone: "text-purple",
        },
        {
            label: "Риски зависимостей",
            value: summary.dependency_risks,
            icon: <GitMerge size={14} aria-hidden="true" />,
            tone: "text-danger",
        },
    ];

    return (
        <aside className="rounded-lg border border-line bg-surface p-3 shadow-card">
            <div className="mb-2 flex items-center justify-between">
                <h3 className="text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">
                    Пульс проекта
                </h3>
                <span className="size-1.5 rounded-full bg-accent shadow-[0_0_8px_var(--color-accent)]" />
            </div>
            <div className="grid gap-1.5 sm:grid-cols-3 lg:grid-cols-1">
                {signals.map((signal) => (
                    <div
                        key={signal.label}
                        className="flex items-center gap-2 rounded-md border border-line-subtle bg-surface-2 px-2.5 py-2"
                    >
                        <span className={signal.tone}>{signal.icon}</span>
                        <span className="min-w-0 flex-1 truncate text-[11px] text-muted">
                            {signal.label}
                        </span>
                        <strong className={`font-mono text-sm ${signal.tone}`}>
                            {signal.value}
                        </strong>
                    </div>
                ))}
            </div>
        </aside>
    );
}
