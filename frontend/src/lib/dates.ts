/** Работа с датами: единые правила отображения сроков во всех представлениях. */

export type DueTone = "muted" | "warning" | "danger";

const DUE_SOON_DAYS = 7;

const DAY_MONTH = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "short" });
const FULL_DATE = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
});
const DATE_TIME = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
});

function startOfToday(): Date {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function parseDate(value: string): Date | null {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** Возвращает число дней от сегодня до даты: отрицательное значит просрочку. */
export function daysUntil(value: string): number | null {
    const target = parseDate(value);
    if (target === null) {
        return null;
    }
    const day = new Date(target.getFullYear(), target.getMonth(), target.getDate());
    return Math.round((day.getTime() - startOfToday().getTime()) / 86_400_000);
}

/**
 * Тон срока: обычный будущий — приглушённый, близкий — предупреждение,
 * просроченный — опасность (раздел 9 дизайн-гайда).
 */
export function dueTone(value: string | null, isDone = false): DueTone {
    if (value === null || isDone) {
        return "muted";
    }
    const days = daysUntil(value);
    if (days === null) {
        return "muted";
    }
    if (days < 0) {
        return "danger";
    }
    return days <= DUE_SOON_DAYS ? "warning" : "muted";
}

export function formatDayMonth(value: string): string {
    const parsed = parseDate(value);
    return parsed === null ? value : DAY_MONTH.format(parsed).replace(".", "");
}

export function formatFullDate(value: string): string {
    const parsed = parseDate(value);
    return parsed === null ? value : FULL_DATE.format(parsed);
}

export function formatDateTime(value: string): string {
    const parsed = parseDate(value);
    return parsed === null ? value : DATE_TIME.format(parsed);
}

/** Короткое относительное время для лент активности: «5 мин назад». */
export function formatRelative(value: string): string {
    const parsed = parseDate(value);
    if (parsed === null) {
        return value;
    }
    const diffMinutes = Math.round((Date.now() - parsed.getTime()) / 60_000);
    if (diffMinutes < 1) {
        return "только что";
    }
    if (diffMinutes < 60) {
        return `${diffMinutes} мин назад`;
    }
    const diffHours = Math.round(diffMinutes / 60);
    if (diffHours < 24) {
        return `${diffHours} ч назад`;
    }
    const diffDays = Math.round(diffHours / 24);
    if (diffDays < 30) {
        return `${diffDays} дн назад`;
    }
    return formatDayMonth(value);
}

/** Значение для input[type=date] из ISO-строки. */
export function toDateInputValue(value: string | null): string {
    if (value === null) {
        return "";
    }
    return value.slice(0, 10);
}
