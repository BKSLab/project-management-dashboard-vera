/**
 * Гант рядом с календарём и его выгрузка (docs/calendar-ui.md, раздел «Рядом» и «Выгрузка»):
 * чистые функции без React — масштаб колёсиком, «Уместить проект», диапазон всего срока,
 * склейка ответов календаря по кускам, легенда цветов, колонки левой части шкалы.
 * Покрыты тестами (ganttView.test.ts).
 */
import { addDateDays, calendarDaysBetween, type TimelineRange, type TimelineScale } from "@/lib/calendar";
import { COLOR_MODE_LABELS, taskColor, type ColorMode } from "@/lib/calendarGrid";
import { dataColor } from "@/lib/dataColor";
import type { CalendarStage, CalendarTask, ProjectCalendar } from "@/lib/types";

/** Ширина дня на шкале, px — общая для шкалы, «Уместить проект» и выгрузки. */
export const TIMELINE_DAY_WIDTH: Record<TimelineScale, number> = {
    week: 104,
    month: 38,
    quarter: 20,
    // Год: деление — неделя (7 × 4 px), подписи — месяцы.
    year: 4,
};

export const TIMELINE_SCALE_ORDER: readonly TimelineScale[] = ["week", "month", "quarter", "year"];

/** Ctrl+колесо: вниз (direction > 0) — мельче (к году), вверх — крупнее (к неделе). */
export function nextTimelineScale(scale: TimelineScale, direction: number): TimelineScale {
    const index = TIMELINE_SCALE_ORDER.indexOf(scale);
    if (direction === 0 || index < 0) return scale;
    const next = Math.min(TIMELINE_SCALE_ORDER.length - 1, Math.max(0, index + Math.sign(direction)));
    return TIMELINE_SCALE_ORDER[next];
}

/** Самый крупный масштаб, при котором `days` дней влезают в `width` px; не влезает никуда — год. */
export function fitTimelineScale(days: number, width: number): TimelineScale {
    for (const scale of TIMELINE_SCALE_ORDER) {
        if (days * TIMELINE_DAY_WIDTH[scale] <= width) return scale;
    }
    return "year";
}

/**
 * Режим показа: шкала растягивается на всю ширину экрана. Ширина дня — сколько влезает
 * (от 4 до 104 px), подписи шапки — от масштаба, которому эта ширина ближе всего снизу.
 */
export function stretchDayWidth(days: number, width: number): { scale: TimelineScale; dayWidth: number } {
    const dayWidth = Math.min(TIMELINE_DAY_WIDTH.week, Math.max(TIMELINE_DAY_WIDTH.year, Math.floor(width / Math.max(1, days))));
    const scale: TimelineScale = dayWidth >= TIMELINE_DAY_WIDTH.week ? "week" : dayWidth >= TIMELINE_DAY_WIDTH.month ? "month" : dayWidth >= 12 ? "quarter" : "year";
    return { scale, dayWidth };
}

interface SpanSource {
    project: { start_date: string | null; due_date: string | null };
    tasks: { start_date: string | null; due_date: string | null }[];
    milestones: { due_date: string }[];
}

/** Самый длинный срок, который покажет шкала: не больше пяти лет, чтобы ошибка в дате не рисовала века. */
export const MAX_SPAN_DAYS = 5 * 366;

/**
 * Весь срок проекта: от самого раннего начала/срока (задачи, проект) до самого позднего
 * срока задачи, вехи или дедлайна проекта; по краям — запас в 2 дня, чтобы полосы не липли к краю.
 * Нет ни одной даты — null.
 */
export function projectSpan({ project, tasks, milestones }: SpanSource): TimelineRange | null {
    const dates: string[] = [];
    for (const value of [project.start_date, project.due_date]) if (value) dates.push(value);
    for (const task of tasks) {
        if (task.start_date) dates.push(task.start_date);
        if (task.due_date) dates.push(task.due_date);
    }
    for (const milestone of milestones) dates.push(milestone.due_date);
    if (dates.length === 0) return null;
    dates.sort();
    const from = addDateDays(dates[0], -2);
    let to = addDateDays(dates.at(-1) as string, 2);
    if (calendarDaysBetween(from, to) > MAX_SPAN_DAYS) to = addDateDays(from, MAX_SPAN_DAYS);
    return { dateFrom: from, dateTo: to };
}

export function rangeDays(range: TimelineRange): number {
    return calendarDaysBetween(range.dateFrom, range.dateTo) + 1;
}

export function unionRange(first: TimelineRange, second: TimelineRange): TimelineRange {
    return {
        dateFrom: first.dateFrom < second.dateFrom ? first.dateFrom : second.dateFrom,
        dateTo: first.dateTo > second.dateTo ? first.dateTo : second.dateTo,
    };
}

/** Сервис отдаёт календарь не больше чем за 371 день — длинный срок режем на куски. */
export const CALENDAR_CHUNK_DAYS = 371;

export function splitRange(range: TimelineRange, chunkDays = CALENDAR_CHUNK_DAYS): TimelineRange[] {
    const chunks: TimelineRange[] = [];
    let from = range.dateFrom;
    while (from <= range.dateTo) {
        const last = addDateDays(from, chunkDays - 1);
        const to = last < range.dateTo ? last : range.dateTo;
        chunks.push({ dateFrom: from, dateTo: to });
        from = addDateDays(to, 1);
    }
    return chunks;
}

/**
 * Склейка ответов календаря за соседние куски: задачи и зависимости — без повторов по id,
 * вехи — по id и дате; сводка, стадии и исполнители не зависят от периода — берутся из первого.
 */
export function mergeProjectCalendars(parts: ProjectCalendar[]): ProjectCalendar {
    if (parts.length === 1) return parts[0];
    const [first] = parts;
    const tasks = new Map<number, CalendarTask>();
    const dependencies = new Map<number, ProjectCalendar["dependencies"][number]>();
    const milestones = new Map<string, ProjectCalendar["milestones"][number]>();
    for (const part of parts) {
        for (const task of part.tasks) tasks.set(task.id, task);
        for (const dependency of part.dependencies) dependencies.set(dependency.id, dependency);
        for (const milestone of part.milestones) {
            milestones.set(`${milestone.is_system ? "system" : milestone.id}:${milestone.due_date}`, milestone);
        }
    }
    return {
        ...first,
        range: { ...first.range, date_to: parts.at(-1)?.range.date_to ?? first.range.date_to },
        tasks: [...tasks.values()],
        dependencies: [...dependencies.values()],
        milestones: [...milestones.values()],
    };
}

// ---------------------------------------------------------------- легенда

export interface LegendItem {
    label: string;
    color: string;
}

const STATUS_LEGEND: LegendItem[] = [
    { label: "В работе", color: "var(--color-info)" },
    { label: "Срок ≤ 7 дн.", color: "var(--color-warning)" },
    { label: "Просрочено", color: "var(--color-danger)" },
    { label: "Готово", color: "var(--color-success)" },
];

/** Легенда цветов полос для выбранного «Цвет по»: только то, что есть среди показанных задач. */
export function timelineLegend(
    mode: ColorMode,
    tasks: CalendarTask[],
    stagesById: ReadonlyMap<number, CalendarStage>,
): { title: string; items: LegendItem[] } {
    const title = `Цвет по ${COLOR_MODE_LABELS[mode]}`;
    if (mode === "stage") {
        const used = new Set(tasks.map((task) => task.stage_id));
        const items = [...stagesById.values()]
            .filter((stage) => used.has(stage.id))
            .sort((first, second) => first.order_index - second.order_index || first.id - second.id)
            .map((stage) => ({ label: stage.name, color: dataColor(stage.color) ?? "var(--color-text-muted)" }));
        return { title, items };
    }
    if (mode === "assignee") {
        const names = [...new Set(tasks.map((task) => task.assignee))].sort((first, second) =>
            first === null ? 1 : second === null ? -1 : first.localeCompare(second, "ru"),
        );
        const items = names.map((name) => ({
            label: name ?? "Без исполнителя",
            color: taskColor({ ...(tasks[0] as CalendarTask), assignee: name }, "assignee"),
        }));
        return { title, items };
    }
    return { title, items: STATUS_LEGEND };
}

// ---------------------------------------------------------------- колонки и подписи

/** Инициалы для кружка на конце полосы: «Иванова Анна» → «ИА», «a.ivanova» → «A». */
export function assigneeInitials(name: string | null | undefined): string | null {
    const words = (name ?? "").trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) return null;
    return words
        .slice(0, 2)
        .map((word) => word[0].toUpperCase())
        .join("");
}

export type GanttColumn = "assignee" | "start" | "due" | "days";

export const GANTT_COLUMNS: { id: GanttColumn; label: string; header: string; width: number }[] = [
    { id: "assignee", label: "Исполнитель", header: "Исп.", width: 92 },
    { id: "start", label: "Начало", header: "Начало", width: 50 },
    { id: "due", label: "Срок", header: "Срок", width: 50 },
    { id: "days", label: "Длительность, дн.", header: "Дн.", width: 34 },
];

export function normalizeGanttColumns(value: unknown): GanttColumn[] {
    if (!Array.isArray(value)) return [];
    return GANTT_COLUMNS.map((column) => column.id).filter((id) => value.includes(id));
}

export function ganttColumnsWidth(columns: readonly GanttColumn[]): number {
    return GANTT_COLUMNS.filter((column) => columns.includes(column.id)).reduce((sum, column) => sum + column.width, 0);
}

/** «2026-09-30» → «30.09». */
export function shortDay(value: string | null): string {
    return value ? `${value.slice(8, 10)}.${value.slice(5, 7)}` : "—";
}

export function ganttCellValue(task: CalendarTask, column: GanttColumn): string {
    if (column === "assignee") return task.assignee ?? "—";
    if (column === "start") return shortDay(task.start_date ?? task.due_date);
    if (column === "due") return shortDay(task.due_date);
    const from = task.start_date ?? task.due_date;
    const to = task.due_date ?? task.start_date;
    return from && to ? String(calendarDaysBetween(from, to) + 1) : "—";
}

export const LABEL_WIDTH_MIN = 180;
export const LABEL_WIDTH_MAX = 480;
export const LABEL_WIDTH_DEFAULT = 210;

export function clampLabelWidth(value: unknown): number {
    const number = typeof value === "number" && Number.isFinite(value) ? value : LABEL_WIDTH_DEFAULT;
    return Math.round(Math.min(LABEL_WIDTH_MAX, Math.max(LABEL_WIDTH_MIN, number)));
}

/** Доля сетки в виде «Рядом»: 20–80 %, по умолчанию половина. */
export function clampSplitRatio(value: unknown): number {
    const number = typeof value === "number" && Number.isFinite(value) ? value : 0.5;
    return Math.min(0.8, Math.max(0.2, number));
}

/** Имя файла выгрузки: «DEMO-гант-2026-09-30.png». */
export function exportFileName(projectKey: string, today: string, extension: "png" | "pdf"): string {
    const safeKey = projectKey.replace(/[^\p{L}\p{N}_-]+/gu, "_") || "project";
    return `${safeKey}-гант-${today}.${extension}`;
}

/** Страница PDF под размер картинки (мм, 96 dpi), не меньше A4 по короткой стороне. */
export function pdfPageSize(widthPx: number, heightPx: number): { width: number; height: number; orientation: "l" | "p" } {
    const mm = 25.4 / 96;
    const width = widthPx * mm;
    const height = heightPx * mm;
    const minShort = 210;
    const scale = Math.max(1, minShort / Math.min(width, height));
    return {
        width: Math.round(width * scale * 10) / 10,
        height: Math.round(height * scale * 10) / 10,
        orientation: width >= height ? "l" : "p",
    };
}
