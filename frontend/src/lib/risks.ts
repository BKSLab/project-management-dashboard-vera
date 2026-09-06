import { formatDateOnly, parseDateOnly } from "@/lib/dates";

export const RISK_RATINGS = ["LOW", "MEDIUM", "HIGH"] as const;
export type RiskRating = typeof RISK_RATINGS[number];
export type RiskStatus = "OPEN" | "MITIGATING" | "OCCURRED" | "CLOSED";
export type RiskStrategy = "AVOID" | "MITIGATE" | "TRANSFER" | "ACCEPT";
export type RiskSource = "MANUAL" | "AI_SUGGESTED";
export type RiskReasonCode = "HIGH_OPEN_RISK" | "RISK_REVIEW_OVERDUE" | "RISK_WITHOUT_OWNER" | "RISK_WITHOUT_MITIGATION" | "RISK_OCCURRED";

export interface RiskInput {
    title: string;
    description: string;
    probability: RiskRating;
    impact: RiskRating;
    status: RiskStatus;
    response_strategy: RiskStrategy;
    mitigation_plan: string;
    response_plan: string;
    owner_user_id: number | null;
    task_id: number | null;
    review_date: string | null;
    source: RiskSource;
}

export interface ProjectRisk extends RiskInput {
    id: number;
    key: string;
    project_id: number;
    risk_level: RiskRating;
    created_at: string;
    updated_at: string;
}

export interface RiskPage {
    items: ProjectRisk[];
    total: number;
    page: number;
    page_size: number;
}

export interface RiskMatrixCell {
    probability: RiskRating;
    impact: RiskRating;
    count: number;
}

export interface RiskSummary {
    total_risks: number;
    active_risks: number;
    open_risks: number;
    mitigating_risks: number;
    occurred_risks: number;
    closed_risks: number;
    high_risks: number;
    medium_risks: number;
    low_risks: number;
    risks_without_owner: number;
    risks_without_mitigation: number;
    risks_due_for_review: number;
    risks_review_overdue: number;
    risks_linked_to_tasks: number;
    ai_suggested_risks: number;
    latest_update: string | null;
    matrix: RiskMatrixCell[];
    signals: { code: RiskReasonCode; count: number }[];
}

export interface RiskSuggestion {
    title: string;
    description: string;
    probability: RiskRating;
    impact: RiskRating;
    response_strategy: RiskStrategy;
    mitigation_plan: string;
    response_plan: string;
    task_id: number | null;
    evidence: string[];
}

export const PROBABILITY_LABELS: Record<RiskRating, string> = { LOW: "Низкая", MEDIUM: "Средняя", HIGH: "Высокая" };
export const IMPACT_LABELS: Record<RiskRating, string> = { LOW: "Низкое", MEDIUM: "Среднее", HIGH: "Высокое" };
export const RISK_LEVEL_LABELS: Record<RiskRating, string> = { LOW: "Низкий", MEDIUM: "Средний", HIGH: "Высокий" };
export const RISK_TONES: Record<RiskRating, string> = { LOW: "text-secondary", MEDIUM: "text-warning", HIGH: "text-danger" };
export const RISK_STATUS_LABELS: Record<RiskStatus, string> = { OPEN: "Открыт", MITIGATING: "Снижается", OCCURRED: "Реализовался", CLOSED: "Закрыт" };
export const RISK_STRATEGY_LABELS: Record<RiskStrategy, string> = { AVOID: "Избежать", MITIGATE: "Снизить", TRANSFER: "Передать", ACCEPT: "Принять" };
export const RISK_SIGNAL_LABELS: Record<RiskReasonCode, string> = {
    HIGH_OPEN_RISK: "Высокие открытые риски",
    RISK_REVIEW_OVERDUE: "Просрочен контроль",
    RISK_WITHOUT_OWNER: "Без ответственного",
    RISK_WITHOUT_MITIGATION: "Без плана митигации",
    RISK_OCCURRED: "Событие реализовалось",
};

/** Только предпросмотр формы. Сохранённый уровень всегда читается из API. */
export function previewRiskLevel(probability: RiskRating, impact: RiskRating): RiskRating {
    const matrix: Record<RiskRating, Record<RiskRating, RiskRating>> = {
        LOW: { LOW: "LOW", MEDIUM: "LOW", HIGH: "MEDIUM" },
        MEDIUM: { LOW: "LOW", MEDIUM: "MEDIUM", HIGH: "HIGH" },
        HIGH: { LOW: "MEDIUM", MEDIUM: "HIGH", HIGH: "HIGH" },
    };
    return matrix[probability][impact];
}

/** Явный список полей защищает запрос от отправки risk_level, ID и времени. */
export function riskInput(value: Partial<RiskInput> = {}): RiskInput {
    return {
        title: (value.title ?? "").trim(), description: (value.description ?? "").trim(),
        probability: value.probability ?? "MEDIUM", impact: value.impact ?? "MEDIUM",
        status: value.status ?? "OPEN", response_strategy: value.response_strategy ?? "MITIGATE",
        mitigation_plan: (value.mitigation_plan ?? "").trim(), response_plan: (value.response_plan ?? "").trim(),
        owner_user_id: value.owner_user_id ?? null, task_id: value.task_id ?? null,
        review_date: value.review_date || null, source: value.source ?? "MANUAL",
    };
}

export function riskFormError(value: RiskInput): string | null {
    if (!value.title.trim() || !value.description.trim()) return "Заполните название и описание риска.";
    if (value.title.trim().length > 255) return "Название должно быть не длиннее 255 символов.";
    if ([value.description, value.mitigation_plan, value.response_plan].some((text) => text.length > 20000)) return "Текст поля должен быть не длиннее 20 000 символов.";
    if (value.review_date && !parseDateOnly(value.review_date)) return "Укажите корректную дату контроля.";
    return null;
}

export function riskChanges(before: RiskInput, after: RiskInput): Partial<Omit<RiskInput, "source">> {
    const normalized = riskInput(after);
    return Object.fromEntries(Object.entries(normalized).filter(([key, value]) => key !== "source" && before[key as keyof RiskInput] !== value));
}

export function isRiskReviewDue(risk: Pick<RiskInput, "status" | "review_date">, today = formatDateOnly(new Date())): boolean {
    return risk.status !== "CLOSED" && risk.review_date !== null && risk.review_date <= today;
}

export function riskQuery(values: Record<string, string | number | boolean | null | undefined>): string {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(values)) {
        if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
    }
    return query.toString();
}
