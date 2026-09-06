import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
    Activity,
    CircleCheckBig,
    Flame,
    History,
    Info,
    Lightbulb,
    RefreshCw,
    ShieldAlert,
    Sparkles,
} from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDateTime, formatRelative } from "@/lib/dates";
import { reportFreshness } from "@/lib/pulse";
import type { AnalyticsHealth, AnalyticsReport } from "@/lib/types";
import { ANALYTICS_HEALTH_LABELS } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorMessage, Skeleton } from "@/components/ui/States";
import {
    FindingCard,
    ProgressCard,
    RecommendationCard,
} from "@/components/dashboard/AnalyticsCards";

/**
 * Оценка состояния красит весь блок, а не только свой значок: цифры и вывод
 * модели относятся к одному организму и должны читаться как одно целое.
 */
const HEALTH_STYLES: Record<AnalyticsHealth, { badge: string; strip: string }> = {
    STABLE: { badge: "border-success/30 bg-success/10 text-success", strip: "bg-success/70" },
    WATCH: { badge: "border-accent-border bg-accent-soft text-accent", strip: "bg-accent/70" },
    RISK: { badge: "border-warning/30 bg-warning/10 text-warning", strip: "bg-warning/75" },
    CRITICAL: { badge: "border-danger/35 bg-danger/12 text-danger", strip: "bg-danger/80" },
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
const SIGNAL_ROWS: { key: "high_risks" | "occurred_risks" | "risks_review_overdue" | "risks_without_owner" | "risks_without_mitigation" | "overdue_tasks" | "milestones_at_risk" | "due_soon_tasks" | "blocked_tasks" | "stale_tasks" | "no_due_date_tasks" | "unassigned_tasks" | "unplaced_tasks"; label: string; tone: string }[] = [
    { key: "high_risks", label: "высокие риски", tone: "text-danger" },
    { key: "occurred_risks", label: "риски реализовались", tone: "text-danger" },
    { key: "risks_review_overdue", label: "риски: просрочен контроль", tone: "text-warning" },
    { key: "risks_without_owner", label: "риски без ответственного", tone: "text-secondary" },
    { key: "risks_without_mitigation", label: "риски без митигации", tone: "text-secondary" },
    { key: "overdue_tasks", label: "просрочено", tone: "text-danger" },
    { key: "milestones_at_risk", label: "вехи под угрозой", tone: "text-danger" },
    { key: "due_soon_tasks", label: "срок на неделе", tone: "text-warning" },
    { key: "blocked_tasks", label: "заблокировано", tone: "text-warning" },
    { key: "stale_tasks", label: "без движения 2 недели", tone: "text-secondary" },
    { key: "no_due_date_tasks", label: "без срока", tone: "text-secondary" },
    { key: "unassigned_tasks", label: "без исполнителя", tone: "text-secondary" },
    { key: "unplaced_tasks", label: "вне ИСР", tone: "text-secondary" },
];

/**
 * Тексты области. Портфель и проект отвечают на разные вопросы, поэтому
 * различаются и заголовком, и тем, что обещают показать.
 */
const SCOPE_COPY = {
    portfolio: {
        title: "Пульс портфеля",
        subtitle: "Состояние активных проектов: где горит и за что браться первым",
        unit: "проектам",
        introTitle: "Цифры собраны — нужна трактовка",
        introText:
            "Разбор сравнивает активные проекты между собой: где сорваны сроки, где работа встала и за какой проект браться сегодня.",
        pendingText:
            "Читаю задачи, риски, документы, обсуждения и планы активных проектов. Сопоставляю их с показателями и командой.",
        findings: "Где горит",
        progress: "Где движется",
        recommendations: "За что взяться",
        emptyFindings: "Проектов, требующих вмешательства, модель не нашла.",
        emptyProgress: "Заметного движения по проектам за последнее время нет.",
        emptyRecommendations: "Перераспределять усилия между проектами не нужно.",
    },
    project: {
        title: "Пульс проекта",
        subtitle: "Работы, риски, команда и документы одним разбором",
        unit: "данным проекта",
        introTitle: "Цифры собраны — нужна трактовка",
        introText:
            "Разбор показывает, что и где просрочено, что сделано и как это шло по комментариям, и какие организационные шаги стоит сделать.",
        pendingText:
            "Читаю задачи, риски, документы, обсуждения, структуру работ и вехи. Проверяю сроки, связи и ответственных.",
        findings: "Что горит",
        progress: "Что сделано",
        recommendations: "Что делать",
        emptyFindings: "Проблем, требующих решения, модель не нашла.",
        emptyProgress: "Заметных результатов за последнее время нет.",
        emptyRecommendations: "Организационных действий не требуется.",
    },
} as const;

type ScopeCopy = (typeof SCOPE_COPY)[keyof typeof SCOPE_COPY];

interface PulseBoardProps {
    /** Проект разбора; без него разбирается портфель активных проектов. */
    projectId?: number | null;
    /** Числовые показатели области: они верны всегда и не ждут модели. */
    metrics?: ReactNode;
    /** Разрез области: стадии проекта или охват разбора — по чему он идёт. */
    breakdown?: ReactNode;
    /** Факты области из базы: задачи, требующие решения прямо сейчас. */
    facts?: ReactNode;
    /** Время последнего изменения данных области: по нему видно, не устарел ли вывод. */
    dataUpdatedAt?: string | null;
    /** Причина, по которой разбор невозможен; кнопка выключается вместе с ней. */
    blockedReason?: string;
    onOpenTask: (taskId: number) => void;
}

/**
 * Пульс — единый блок состояния: показатели, факты и их трактовка на одной
 * поверхности.
 *
 * Раньше цифры жили отдельной полосой сверху, список требующих внимания
 * задач — своей секцией ниже, а разбор модели — третьим блоком, и связь
 * между ними приходилось достраивать самому. Здесь всё идёт одним потоком:
 * полоса состояния, показатели, разрез области, поимённые факты и вывод
 * модели с его основаниями.
 */
export function PulseBoard({
    projectId = null,
    metrics,
    breakdown,
    facts,
    dataUpdatedAt = null,
    blockedReason,
    onOpenTask,
}: PulseBoardProps) {
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
    const health = report ? HEALTH_STYLES[report.health] : null;
    const HealthIcon = report ? HEALTH_ICONS[report.health] : null;
    const freshness = reportFreshness(report?.created_at, dataUpdatedAt);
    const blocked = Boolean(blockedReason);

    return (
        <section
            className={cn(
                "ai-surface flex min-w-0 flex-col overflow-hidden",
                "rounded-[var(--radius-panel)] border border-ai-border shadow-card",
            )}
        >
            {/* Полоса состояния окрашивает блок целиком: оценка относится и к
                показателям, и к выводу, а не к одному абзацу текста. */}
            <div
                className={cn(
                    "h-[3px] w-full transition-colors duration-[var(--duration-normal)]",
                    health ? health.strip : "bg-ai-border",
                )}
            />

            <header className="flex flex-wrap items-center gap-3 px-4 py-3">
                <span className="ai-mark flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-control)] text-ai-blue">
                    <Sparkles size={16} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-[13px] font-semibold text-primary">{copy.title}</h2>
                        {report && health && HealthIcon && (
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
                        )}
                    </div>
                    <p className="truncate text-[11px] text-muted">{copy.subtitle}</p>
                </div>
                <div className="flex items-center gap-3">
                    {!generate.isPending && (
                        <PulseAge report={report} freshness={freshness} blocked={blockedReason} />
                    )}
                    <Button
                        variant="primary"
                        onClick={() => generate.mutate()}
                        disabled={generate.isPending || blocked}
                        title={blockedReason}
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
                              ? "Обновить разбор"
                              : "Разобрать"}
                    </Button>
                </div>
            </header>

            {metrics && <div className="border-t border-line-subtle">{metrics}</div>}
            {breakdown && (
                <div className="border-t border-line-subtle px-4 py-3.5">{breakdown}</div>
            )}
            {/* Факты из базы стоят между показателями и выводом модели: это
                то же состояние, только названное поимённо. Отдельной секцией
                ниже они выглядели как ещё один, ни с чем не связанный список. */}
            {facts && <div className="border-t border-line-subtle px-4 py-3.5">{facts}</div>}

            {generate.error && (
                <div className="border-t border-line-subtle px-4 pt-3">
                    <ErrorMessage
                        title="Разбор не сформирован"
                        message={(generate.error as Error).message}
                    />
                </div>
            )}

            {reportQuery.isPending ? (
                <PulseSkeleton />
            ) : report ? (
                <PulseVerdict
                    report={report}
                    copy={copy}
                    stale={generate.isPending}
                    onOpenTask={onOpenTask}
                />
            ) : (
                <PulseIntro pending={generate.isPending} copy={copy} />
            )}
        </section>
    );
}

interface PulseAgeProps {
    report: AnalyticsReport | null;
    freshness: ReturnType<typeof reportFreshness>;
    blocked?: string;
}

/**
 * Отметка свежести рядом с кнопкой: когда сделан разбор и не устарел ли он.
 *
 * Старый вывод выглядит так же уверенно, как только что сделанный, поэтому
 * возраст стоит рядом с действием, которое его обновляет.
 */
function PulseAge({ report, freshness, blocked }: PulseAgeProps) {
    if (blocked) {
        return <span className="hidden text-[11px] text-muted sm:inline">{blocked}</span>;
    }
    if (!report) {
        return <span className="hidden text-[11px] text-disabled sm:inline">Разбора ещё не было</span>;
    }
    return (
        <span
            className={cn(
                "hidden items-center gap-1.5 text-[11px] sm:inline-flex",
                freshness === "stale" ? "text-warning" : "text-muted",
            )}
        >
            <History size={11} aria-hidden="true" />
            {freshness === "stale"
                ? `данные менялись после разбора (${formatRelative(report.created_at)})`
                : `разбор ${formatRelative(report.created_at)}`}
        </span>
    );
}

function PulseSkeleton() {
    return (
        <div
            role="status"
            aria-label="Загрузка разбора"
            className="flex flex-col gap-3 border-t border-line-subtle p-4"
        >
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

function PulseIntro({ pending, copy }: { pending: boolean; copy: ScopeCopy }) {
    return (
        <div className="flex flex-col items-center gap-3 border-t border-line-subtle px-6 py-9 text-center">
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

interface PulseVerdictProps {
    report: AnalyticsReport;
    copy: ScopeCopy;
    stale: boolean;
    onOpenTask: (taskId: number) => void;
}

function PulseVerdict({ report, copy, stale, onOpenTask }: PulseVerdictProps) {
    const signals = SIGNAL_ROWS.filter((row) => (report.signals[row.key] ?? 0) > 0);

    return (
        <div
            className={cn(
                "flex min-w-0 flex-col border-t border-line-subtle",
                "transition-opacity duration-[var(--duration-normal)]",
                stale && "opacity-45",
            )}
        >
            <div className="flex flex-col gap-3 px-4 py-4">
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
                                <span
                                    className={cn(
                                        "font-mono text-[13px] font-semibold",
                                        row.tone,
                                    )}
                                >
                                    {report.signals[row.key]}
                                </span>
                                <span className="text-muted">{row.label}</span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="grid gap-x-4 gap-y-5 border-t border-line-subtle px-4 py-4 lg:grid-cols-2 xl:grid-cols-3">
                <PulseColumn
                    title={copy.findings}
                    icon={<Flame size={12} aria-hidden="true" />}
                    count={report.findings.length}
                    empty={copy.emptyFindings}
                >
                    {report.findings.map((finding, index) => (
                        <FindingCard
                            key={`${finding.title}-${index}`}
                            finding={finding}
                            onOpenTask={onOpenTask}
                        />
                    ))}
                </PulseColumn>

                <PulseColumn
                    title={copy.progress}
                    icon={<CircleCheckBig size={12} aria-hidden="true" />}
                    count={report.progress.length}
                    empty={copy.emptyProgress}
                >
                    {report.progress.map((progress, index) => (
                        <ProgressCard
                            key={`${progress.title}-${index}`}
                            progress={progress}
                            onOpenTask={onOpenTask}
                        />
                    ))}
                </PulseColumn>

                <PulseColumn
                    title={copy.recommendations}
                    icon={<Lightbulb size={12} aria-hidden="true" />}
                    count={report.recommendations.length}
                    empty={copy.emptyRecommendations}
                >
                    {report.recommendations.map((recommendation, index) => (
                        <RecommendationCard
                            key={`${recommendation.title}-${index}`}
                            recommendation={recommendation}
                            onOpenTask={onOpenTask}
                        />
                    ))}
                </PulseColumn>
            </div>

            <PulseFooter report={report} unit={copy.unit} />
        </div>
    );
}

interface PulseColumnProps {
    title: string;
    icon: ReactNode;
    count: number;
    empty: string;
    children: ReactNode;
}

function PulseColumn({ title, icon, count, empty, children }: PulseColumnProps) {
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
                // Высота колонки ограничена: разбор из десятка карточек иначе
                // уводит проекты и списки задач за пределы экрана, и страница
                // перестаёт читаться целиком.
                <div className="scrollbar-thin flex max-h-96 flex-col gap-2 overflow-y-auto pr-0.5">
                    {children}
                </div>
            )}
        </div>
    );
}

function PulseFooter({ report, unit }: { report: AnalyticsReport; unit: string }) {
    const { context } = report;
    const included = [
        `${context.tasks_included} из ${context.tasks_total} задач`,
        context.comments_included > 0 && `${context.comments_included} комментариев`,
        context.milestones_included > 0 && `${context.milestones_included} вех`,
        context.wbs_nodes_included > 0 && `${context.wbs_nodes_included} разделов ИСР`,
        context.stickers_included > 0 && `${context.stickers_included} стикеров`,
        context.documents_included > 0 && `${context.documents_included} документов`,
        (context.risks_total ?? 0) > 0 && `${context.risks_included ?? 0} из ${context.risks_total} рисков`,
        context.activity_included > 0 && `${context.activity_included} событий истории`,
        ...([
            ["members", "участников команды"],
            ["participants", "ролевых назначений"],
            ["attachments", "вложений (метаданные)"],
            ["dependencies", "зависимостей задач"],
            ["checklists", "чек-листов"],
            ["checklist_items", "пунктов чек-листов"],
        ] as const).map(([key, label]) => {
            const count = context.entity_counts?.[key];
            return count && count.total > 0 && `${count.included} из ${count.total} ${label}`;
        }),
    ].filter(Boolean) as string[];

    return (
        <footer className="flex flex-col gap-1.5 border-t border-line-subtle px-4 py-2.5">
            <p className="text-[11px] text-muted">
                Разбор по {unit} · {formatDateTime(report.created_at)} · {report.created_by} ·{" "}
                {report.llm_model} · {Math.round(report.duration_ms / 1000)} с
            </p>
            <p className="text-[11px] text-disabled">В разбор вошли: {included.join(", ")}.</p>
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
