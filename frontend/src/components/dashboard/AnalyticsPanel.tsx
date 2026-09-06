import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
    Activity,
    CircleCheckBig,
    Flame,
    Info,
    Lightbulb,
    RefreshCw,
    ShieldAlert,
    Sparkles,
} from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/dates";
import type { AnalyticsHealth, AnalyticsReport, AnalyticsSignals } from "@/lib/types";
import { ANALYTICS_HEALTH_LABELS } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorMessage, Skeleton } from "@/components/ui/States";
import {
    FindingCard,
    ProgressCard,
    RecommendationCard,
} from "@/components/dashboard/AnalyticsCards";

const HEALTH_STYLES: Record<AnalyticsHealth, { badge: string; dot: string }> = {
    STABLE: { badge: "border-success/30 bg-success/10 text-success", dot: "bg-success" },
    WATCH: { badge: "border-accent-border bg-accent-soft text-accent", dot: "bg-accent" },
    RISK: { badge: "border-warning/30 bg-warning/10 text-warning", dot: "bg-warning" },
    CRITICAL: { badge: "border-danger/35 bg-danger/12 text-danger", dot: "bg-danger" },
};

const HEALTH_ICONS: Record<AnalyticsHealth, typeof Activity> = {
    STABLE: CircleCheckBig,
    WATCH: Activity,
    RISK: ShieldAlert,
    CRITICAL: Flame,
};

/**
 * Факты рядом с текстом свода: по ним видно, на чём основан вывод, и они
 * остаются верными, даже если модель ошиблась в формулировке.
 */
const SIGNAL_ROWS: { key: keyof AnalyticsSignals; label: string; tone: string }[] = [
    { key: "overdue_tasks", label: "просрочено", tone: "text-danger" },
    { key: "milestones_at_risk", label: "вехи под угрозой", tone: "text-danger" },
    { key: "due_soon_tasks", label: "срок на неделе", tone: "text-warning" },
    { key: "blocked_tasks", label: "заблокировано", tone: "text-warning" },
    { key: "stale_tasks", label: "без движения 2 недели", tone: "text-secondary" },
    { key: "no_due_date_tasks", label: "без срока", tone: "text-secondary" },
    { key: "unassigned_tasks", label: "без исполнителя", tone: "text-secondary" },
    { key: "unplaced_tasks", label: "вне ИСР", tone: "text-secondary" },
];

interface AnalyticsPanelProps {
    /** Проект разбора; без него разбирается портфель активных проектов. */
    projectId?: number | null;
    onOpenTask: (taskId: number) => void;
}

/** Тексты области: у портфеля и у проекта разные вопросы к аналитике. */
const SCOPE_COPY = {
    portfolio: {
        title: "Сводка по проектам",
        subtitle: "Состояние активных проектов: где горит и за что браться первым",
        introTitle: "Статистика есть — нужна трактовка",
        introText:
            "Сводка сравнивает активные проекты между собой: где сорваны сроки, где работа встала и за какой проект браться сегодня. Запускается кнопкой — расписания нет.",
        pendingText:
            "Читаю показатели, вехи и проблемные задачи каждого активного проекта. Обычно это занимает до полуминуты.",
    },
    project: {
        title: "Пульс проекта",
        subtitle: "Разбор задач, комментариев, ИСР, доски и документов проекта",
        introTitle: "Статистика есть — нужна трактовка",
        introText:
            "Пульс показывает, что и где просрочено, что сделано и как это шло по комментариям, и какие организационные шаги стоит сделать. Запускается кнопкой — расписания нет.",
        pendingText:
            "Читаю задачи, комментарии, историю изменений, ИСР, стикеры и документы. Обычно это занимает до полуминуты.",
    },
} as const;

/**
 * Аналитика по кнопке: модель разбирает срез и объясняет, что в нём важно.
 * Свод сохраняется на backend, поэтому переживает перезагрузку и виден
 * команде целиком. Область задаётся снаружи: дашборд всегда спрашивает про
 * портфель, страница проекта — только про свой проект.
 */
export function AnalyticsPanel({ projectId = null, onOpenTask }: AnalyticsPanelProps) {
    const queryClient = useQueryClient();
    const copy = projectId ? SCOPE_COPY.project : SCOPE_COPY.portfolio;

    const reportQuery = useQuery({
        queryKey: queryKeys.dashboardAnalytics(projectId),
        queryFn: () => api.get<AnalyticsReport | null>(endpoints.dashboardAnalytics(projectId)),
    });

    const generate = useMutation({
        mutationFn: () =>
            api.post<AnalyticsReport>(endpoints.dashboardAnalytics(), { project_id: projectId }),
        onSuccess: (report) => {
            queryClient.setQueryData(queryKeys.dashboardAnalytics(projectId), report);
        },
    });

    const report = reportQuery.data ?? null;

    return (
        <section
            className={cn(
                "ai-surface flex min-w-0 flex-col overflow-hidden",
                "rounded-[var(--radius-panel)] border border-ai-border shadow-card",
            )}
        >
            <header className="flex flex-wrap items-center gap-3 border-b border-line-subtle px-4 py-3">
                <span className="ai-mark flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-control)] text-ai-blue">
                    <Sparkles size={16} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                    <h2 className="text-[13px] font-semibold text-primary">{copy.title}</h2>
                    <p className="truncate text-[11px] text-muted">{copy.subtitle}</p>
                </div>
                <Button
                    variant="primary"
                    onClick={() => generate.mutate()}
                    disabled={generate.isPending}
                    icon={
                        generate.isPending ? (
                            <RefreshCw size={14} className="animate-spin" aria-hidden="true" />
                        ) : (
                            <Sparkles size={14} aria-hidden="true" />
                        )
                    }
                >
                    {generate.isPending
                        ? "Разбираю…"
                        : report
                          ? "Обновить"
                          : "Сформировать аналитику"}
                </Button>
            </header>

            {generate.error && (
                <div className="px-4 pt-3">
                    <ErrorMessage
                        title="Аналитика не сформирована"
                        message={(generate.error as Error).message}
                    />
                </div>
            )}

            {reportQuery.isPending ? (
                <AnalyticsSkeleton />
            ) : report ? (
                <AnalyticsReportView
                    report={report}
                    stale={generate.isPending}
                    onOpenTask={onOpenTask}
                />
            ) : (
                <AnalyticsIntro pending={generate.isPending} copy={copy} />
            )}
        </section>
    );
}

function AnalyticsSkeleton() {
    return (
        <div role="status" aria-label="Загрузка аналитики" className="flex flex-col gap-3 p-4">
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <div className="grid gap-3 xl:grid-cols-3">
                {[0, 1, 2].map((index) => (
                    <Skeleton key={index} className="h-24" />
                ))}
            </div>
        </div>
    );
}

interface AnalyticsIntroProps {
    pending: boolean;
    copy: (typeof SCOPE_COPY)[keyof typeof SCOPE_COPY];
}

function AnalyticsIntro({ pending, copy }: AnalyticsIntroProps) {
    return (
        <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
            <span className="ai-mark flex size-11 items-center justify-center rounded-[var(--radius-card)] text-ai-blue">
                {pending ? (
                    <RefreshCw size={20} className="animate-spin" aria-hidden="true" />
                ) : (
                    <Sparkles size={20} aria-hidden="true" />
                )}
            </span>
            <div className="flex max-w-lg flex-col gap-1.5">
                <h3 className="text-[15px] font-semibold text-primary">
                    {pending ? "Собираю картину работ" : copy.introTitle}
                </h3>
                <p className="text-[13px] leading-relaxed text-muted">
                    {pending ? copy.pendingText : copy.introText}
                </p>
            </div>
        </div>
    );
}

interface AnalyticsReportViewProps {
    report: AnalyticsReport;
    stale: boolean;
    onOpenTask: (taskId: number) => void;
}

function AnalyticsReportView({ report, stale, onOpenTask }: AnalyticsReportViewProps) {
    const health = HEALTH_STYLES[report.health];
    const HealthIcon = HEALTH_ICONS[report.health];
    const signals = SIGNAL_ROWS.filter((row) => report.signals[row.key] > 0);

    return (
        <div
            className={cn(
                "flex min-w-0 flex-col transition-opacity duration-[var(--duration-normal)]",
                stale && "opacity-45",
            )}
        >
            <div className="flex flex-col gap-3 px-4 py-4">
                <div className="flex flex-wrap items-center gap-2">
                    <span
                        className={cn(
                            "inline-flex items-center gap-1.5 rounded-[5px] border px-2 py-0.5",
                            "text-[11px] font-semibold",
                            health.badge,
                        )}
                    >
                        <HealthIcon size={12} aria-hidden="true" />
                        {ANALYTICS_HEALTH_LABELS[report.health]}
                    </span>
                    <span className="text-[11px] text-muted">
                        <span className="font-mono text-secondary">
                            {report.signals.done_tasks}/{report.signals.total_tasks}
                        </span>{" "}
                        задач закрыто
                    </span>
                </div>
                <p className="max-w-4xl text-[17px] leading-snug font-semibold tracking-[-0.02em] text-primary">
                    {report.headline}
                </p>
                <p className="max-w-4xl text-[13px] leading-relaxed text-secondary">
                    {report.health_note}
                </p>
                {signals.length > 0 && (
                    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 pt-0.5">
                        {signals.map((row) => (
                            <li key={row.key} className="flex items-baseline gap-1.5 text-[11px]">
                                <span className={cn("font-mono text-[13px] font-semibold", row.tone)}>
                                    {report.signals[row.key]}
                                </span>
                                <span className="text-muted">{row.label}</span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="grid gap-x-4 gap-y-5 border-t border-line-subtle px-4 py-4 lg:grid-cols-2 xl:grid-cols-3">
                <AnalyticsColumn
                    title="Что горит"
                    icon={<Flame size={12} aria-hidden="true" />}
                    count={report.findings.length}
                    empty="Проблем, требующих решения, модель не нашла."
                >
                    {report.findings.map((finding, index) => (
                        <FindingCard
                            key={`${finding.title}-${index}`}
                            finding={finding}
                            onOpenTask={onOpenTask}
                        />
                    ))}
                </AnalyticsColumn>

                <AnalyticsColumn
                    title="Что сделано"
                    icon={<CircleCheckBig size={12} aria-hidden="true" />}
                    count={report.progress.length}
                    empty="Заметных результатов за последнее время нет."
                >
                    {report.progress.map((progress, index) => (
                        <ProgressCard
                            key={`${progress.title}-${index}`}
                            progress={progress}
                            onOpenTask={onOpenTask}
                        />
                    ))}
                </AnalyticsColumn>

                <AnalyticsColumn
                    title="Что делать"
                    icon={<Lightbulb size={12} aria-hidden="true" />}
                    count={report.recommendations.length}
                    empty="Организационных действий не требуется."
                >
                    {report.recommendations.map((recommendation, index) => (
                        <RecommendationCard
                            key={`${recommendation.title}-${index}`}
                            recommendation={recommendation}
                            onOpenTask={onOpenTask}
                        />
                    ))}
                </AnalyticsColumn>
            </div>

            <AnalyticsFooter report={report} />
        </div>
    );
}

interface AnalyticsColumnProps {
    title: string;
    icon: React.ReactNode;
    count: number;
    empty: string;
    children: React.ReactNode;
}

function AnalyticsColumn({ title, icon, count, empty, children }: AnalyticsColumnProps) {
    return (
        <div className="flex min-w-0 flex-col gap-2">
            <h3 className="flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
                {icon}
                {title}
                {count > 0 && <span className="font-mono text-[11px] text-disabled">{count}</span>}
            </h3>
            {count === 0 ? (
                <p className="rounded-[var(--radius-card)] bg-app/40 px-3 py-4 text-[12.5px] text-disabled">
                    {empty}
                </p>
            ) : (
                <div className="flex flex-col gap-2">{children}</div>
            )}
        </div>
    );
}

function AnalyticsFooter({ report }: { report: AnalyticsReport }) {
    const { context } = report;
    const included = [
        `${context.tasks_included} из ${context.tasks_total} задач`,
        context.comments_included > 0 && `${context.comments_included} комментариев`,
        context.wbs_nodes_included > 0 && `${context.wbs_nodes_included} разделов ИСР`,
        context.stickers_included > 0 && `${context.stickers_included} стикеров`,
        context.documents_included > 0 && `${context.documents_included} документов`,
    ].filter(Boolean) as string[];

    return (
        <footer className="flex flex-col gap-1.5 border-t border-line-subtle px-4 py-2.5">
            <p className="text-[11px] text-muted">
                {formatDateTime(report.created_at)} · {report.created_by} · {report.llm_model} ·{" "}
                {Math.round(report.duration_ms / 1000)} с
            </p>
            <p className="text-[11px] text-disabled">В анализ вошли: {included.join(", ")}.</p>
            {context.truncated && context.omitted.length > 0 && (
                <details className="text-[11px] text-disabled">
                    <summary className="inline-flex cursor-pointer items-center gap-1 hover:text-muted">
                        <Info size={11} aria-hidden="true" />
                        Часть данных не поместилась в контекст
                    </summary>
                    <ul className="mt-1 flex list-disc flex-col gap-0.5 pl-5">
                        {context.omitted.map((item) => (
                            <li key={item}>{item}</li>
                        ))}
                    </ul>
                </details>
            )}
        </footer>
    );
}
