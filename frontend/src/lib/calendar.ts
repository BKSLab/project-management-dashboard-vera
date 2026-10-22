import { formatDateOnly, parseDateOnly } from "@/lib/dates";
import type { CalendarHoliday, CalendarRiskReason, CalendarTask } from "@/lib/types";

/** Плановые даты задачи — всё, что нужно для раскладки по дням. */
export type DatedTask = Pick<CalendarTask, "start_date" | "due_date">;

export interface CalendarDayModel {
    date: string;
    dayNumber: number;
    inCurrentMonth: boolean;
    isWeekend: boolean;
    isToday: boolean;
    /** Нерабочий день: сб/вс или праздник по производственному календарю, кроме рабочих суббот. */
    isOff: boolean;
    /** Название праздника/сокращённого дня для подсказки. */
    holidayTitle: string | null;
}

export type TimelineScale = "week" | "month" | "quarter" | "year";

/** Отклонения от обычной недели по дате (ответ /calendar/holidays). */
export type HolidayMap = ReadonlyMap<string, CalendarHoliday>;

/** Выходной ли день с учётом праздников и перенесённых рабочих суббот. */
export function dayOffInfo(date: string, holidays?: HolidayMap): { isOff: boolean; title: string | null } {
    const parsed = parseDateOnly(date);
    const dayOfWeek = parsed?.getDay() ?? 1;
    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
    const holiday = holidays?.get(date);
    if (holiday === undefined) return { isOff: isWeekend, title: null };
    if (holiday.kind === "WORKING_DAY") return { isOff: false, title: holiday.title ?? "Рабочий день (перенос)" };
    if (holiday.kind === "SHORT_DAY") return { isOff: false, title: holiday.title ?? "Сокращённый день" };
    return { isOff: true, title: holiday.title ?? (holiday.kind === "HOLIDAY" ? "Праздник" : "Выходной") };
}

function dayModel(date: string, today: string, inCurrentMonth: boolean, holidays?: HolidayMap): CalendarDayModel {
    const parsed = parseDateOnly(date);
    const dayOfWeek = parsed?.getDay() ?? 1;
    const off = dayOffInfo(date, holidays);
    return {
        date,
        dayNumber: parsed?.getDate() ?? 0,
        inCurrentMonth,
        isWeekend: dayOfWeek === 0 || dayOfWeek === 6,
        isToday: date === today,
        isOff: off.isOff,
        holidayTitle: off.title,
    };
}

export interface TimelineRange {
    dateFrom: string;
    dateTo: string;
}

export interface TaskInterval {
    startDate: string;
    dueDate: string;
    durationDays: number;
    openEnd: boolean;
}

export interface TimelineBarGeometry {
    left: number;
    width: number;
    clippedStart: boolean;
    clippedEnd: boolean;
    openEnd: boolean;
}

export interface TimelineDependencyGeometry {
    path: string;
    fromX: number;
    fromY: number;
    toX: number;
    toY: number;
}

const MONTH_TITLE = new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" });
const DAY_TITLE = new Intl.DateTimeFormat("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
});
const RANGE_TITLE = new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
});

export function localToday(): string {
    return formatDateOnly(new Date());
}

export function normalizeMonth(value: string | null, fallback = new Date()): string {
    if (value !== null && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)) {
        return value;
    }
    return formatDateOnly(new Date(fallback.getFullYear(), fallback.getMonth(), 1)).slice(0, 7);
}

export function shiftMonth(month: string, delta: number): string {
    const [year, monthNumber] = month.split("-").map(Number);
    return formatDateOnly(new Date(year, monthNumber - 1 + delta, 1)).slice(0, 7);
}

export function monthTitle(month: string): string {
    const [year, monthNumber] = month.split("-").map(Number);
    const title = MONTH_TITLE.format(new Date(year, monthNumber - 1, 1));
    return title.charAt(0).toUpperCase() + title.slice(1);
}

export function dayTitle(value: string): string {
    const parsed = parseDateOnly(value);
    return parsed === null ? value : DAY_TITLE.format(parsed);
}

export function buildMonthGrid(
    month: string,
    today = localToday(),
    holidays?: HolidayMap,
): CalendarDayModel[] {
    const [year, monthNumber] = month.split("-").map(Number);
    const first = new Date(year, monthNumber - 1, 1);
    const mondayOffset = (first.getDay() + 6) % 7;
    const gridStart = new Date(year, monthNumber - 1, 1 - mondayOffset);
    return Array.from({ length: 42 }, (_, index) => {
        const current = new Date(
            gridStart.getFullYear(),
            gridStart.getMonth(),
            gridStart.getDate() + index,
        );
        return dayModel(formatDateOnly(current), today, current.getMonth() === monthNumber - 1, holidays);
    });
}

export function tasksByDate<T extends DatedTask>(tasks: T[]): Map<string, T[]> {
    const grouped = new Map<string, T[]>();
    for (const task of tasks) {
        const date = task.due_date ?? task.start_date;
        if (date === null) continue;
        const bucket = grouped.get(date) ?? [];
        bucket.push(task);
        grouped.set(date, bucket);
    }
    return grouped;
}

export function rescheduleCalendarTask(
    task: CalendarTask,
    dueDate: string | null,
    today: string,
    startDate: string | null = task.start_date,
): CalendarTask {
    const isOverdue = !task.is_done && dueDate !== null && dueDate < today;
    const soonLimit = parseDateOnly(today);
    if (soonLimit !== null) {
        soonLimit.setDate(soonLimit.getDate() + 7);
    }
    const soonLimitValue = soonLimit === null ? today : formatDateOnly(soonLimit);
    const isDueSoon =
        !task.is_done && dueDate !== null && dueDate >= today && dueDate <= soonLimitValue;
    const riskReasons: CalendarRiskReason[] = [];
    if (!task.is_done && dueDate === null) {
        riskReasons.push({ code: "NO_DUE_DATE", message: "У задачи не задан срок.", days: null });
    } else if (isOverdue && dueDate !== null) {
        const due = parseDateOnly(dueDate);
        const current = parseDateOnly(today);
        const days =
            due === null || current === null
                ? null
                : Math.round((current.getTime() - due.getTime()) / 86_400_000);
        riskReasons.push({
            code: "OVERDUE",
            message: days === null ? "Срок просрочен." : `Срок просрочен на ${days} дн.`,
            days,
        });
    } else if (isDueSoon && dueDate !== null) {
        const due = parseDateOnly(dueDate);
        const current = parseDateOnly(today);
        const days =
            due === null || current === null
                ? null
                : Math.round((due.getTime() - current.getTime()) / 86_400_000);
        riskReasons.push({
            code: "DUE_SOON",
            message: days === 0 ? "Срок сегодня." : `До срока ${days} дн.`,
            days,
        });
    }
    if (!task.is_done && !task.assignee) {
        riskReasons.push({ code: "NO_ASSIGNEE", message: "У задачи нет исполнителя.", days: null });
    }
    const riskLevel = task.is_done
        ? null
        : isOverdue
          ? "high"
          : isDueSoon || dueDate === null
            ? "medium"
            : !task.assignee
              ? "low"
              : null;
    const driftDays =
        dueDate !== null && task.baseline_due_date !== null
            ? calendarDaysBetween(task.baseline_due_date, dueDate)
            : null;
    return {
        ...task,
        start_date: startDate,
        due_date: dueDate,
        is_overdue: isOverdue,
        is_due_soon: isDueSoon,
        drift_days: driftDays,
        risk_level: riskLevel,
        risk_reasons: riskReasons,
    };
}

export function normalizeScale(value: string | null): TimelineScale {
    return value === "week" || value === "quarter" || value === "year" ? value : "month";
}

export function normalizeDate(value: string | null, fallback = localToday()): string {
    return value !== null && parseDateOnly(value) !== null ? value : fallback;
}

export function addDateDays(value: string, days: number): string {
    const parsed = parseDateOnly(value);
    if (parsed === null) return value;
    parsed.setDate(parsed.getDate() + days);
    return formatDateOnly(parsed);
}

export function calendarDaysBetween(first: string, second: string): number {
    const firstParts = first.split("-").map(Number);
    const secondParts = second.split("-").map(Number);
    if (firstParts.length !== 3 || secondParts.length !== 3) return 0;
    const firstUtc = Date.UTC(firstParts[0], firstParts[1] - 1, firstParts[2]);
    const secondUtc = Date.UTC(secondParts[0], secondParts[1] - 1, secondParts[2]);
    return Math.round((secondUtc - firstUtc) / 86_400_000);
}

export function timelineRange(anchor: string, scale: TimelineScale): TimelineRange {
    const parsed = parseDateOnly(anchor) ?? new Date();
    let first: Date;
    let last: Date;
    if (scale === "week") {
        const mondayOffset = (parsed.getDay() + 6) % 7;
        first = new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate() - mondayOffset);
        last = new Date(first.getFullYear(), first.getMonth(), first.getDate() + 6);
    } else if (scale === "year") {
        first = new Date(parsed.getFullYear(), 0, 1);
        last = new Date(parsed.getFullYear(), 11, 31);
    } else if (scale === "quarter") {
        const quarterMonth = Math.floor(parsed.getMonth() / 3) * 3;
        first = new Date(parsed.getFullYear(), quarterMonth, 1);
        last = new Date(parsed.getFullYear(), quarterMonth + 3, 0);
    } else {
        first = new Date(parsed.getFullYear(), parsed.getMonth(), 1);
        last = new Date(parsed.getFullYear(), parsed.getMonth() + 1, 0);
    }
    return { dateFrom: formatDateOnly(first), dateTo: formatDateOnly(last) };
}

export function shiftTimelineAnchor(
    anchor: string,
    scale: TimelineScale,
    delta: number,
): string {
    const parsed = parseDateOnly(anchor) ?? new Date();
    if (scale === "week") parsed.setDate(parsed.getDate() + delta * 7);
    else {
        // С 31-го числа setMonth перескакивает через короткий месяц — число прижимаем к концу месяца.
        const months = delta * (scale === "year" ? 12 : scale === "quarter" ? 3 : 1);
        const target = new Date(parsed.getFullYear(), parsed.getMonth() + months, 1);
        const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
        target.setDate(Math.min(parsed.getDate(), lastDay));
        return formatDateOnly(target);
    }
    return formatDateOnly(parsed);
}

export function timelineTitle(range: TimelineRange, scale: TimelineScale): string {
    if (scale === "month") return monthTitle(range.dateFrom.slice(0, 7));
    const first = parseDateOnly(range.dateFrom);
    const last = parseDateOnly(range.dateTo);
    if (first === null || last === null) return `${range.dateFrom} — ${range.dateTo}`;
    if (scale === "year") return `${first.getFullYear()} год`;
    if (scale === "quarter") {
        const quarter = Math.floor(first.getMonth() / 3) + 1;
        return `${quarter} квартал ${first.getFullYear()}`;
    }
    return `${RANGE_TITLE.format(first)} — ${RANGE_TITLE.format(last)}`;
}

export function buildTimelineDays(
    range: TimelineRange,
    today = localToday(),
    holidays?: HolidayMap,
): CalendarDayModel[] {
    const count = calendarDaysBetween(range.dateFrom, range.dateTo) + 1;
    return Array.from({ length: Math.max(count, 0) }, (_, index) =>
        dayModel(addDateDays(range.dateFrom, index), today, true, holidays),
    );
}

export function taskInterval(task: DatedTask): TaskInterval | null {
    const startDate = task.start_date ?? task.due_date;
    const dueDate = task.due_date ?? task.start_date;
    if (startDate === null || dueDate === null) return null;
    return {
        startDate,
        dueDate,
        durationDays: Math.max(calendarDaysBetween(startDate, dueDate), 0),
        openEnd: task.due_date === null,
    };
}

export function moveTaskInterval(task: DatedTask, targetStart: string) {
    const interval = taskInterval(task);
    if (interval === null) return { startDate: targetStart, dueDate: targetStart };
    if (interval.openEnd) return { startDate: targetStart, dueDate: null };
    if (task.start_date === null) return { startDate: null, dueDate: targetStart };
    return {
        startDate: targetStart,
        dueDate: addDateDays(targetStart, interval.durationDays),
    };
}

export function resizeTaskInterval(
    task: DatedTask,
    edge: "start" | "end",
    deltaDays: number,
) {
    const interval = taskInterval(task);
    if (interval === null) return null;
    if (edge === "start") {
        const startDate = addDateDays(interval.startDate, deltaDays);
        if (interval.openEnd) return { startDate, dueDate: null };
        return startDate <= interval.dueDate
            ? { startDate, dueDate: interval.dueDate }
            : null;
    }
    const dueDate = addDateDays(interval.dueDate, deltaDays);
    return dueDate >= interval.startDate
        ? { startDate: task.start_date, dueDate }
        : null;
}

export function timelineBarGeometry(
    task: DatedTask,
    range: TimelineRange,
    dayWidth: number,
): TimelineBarGeometry | null {
    const interval = taskInterval(task);
    if (
        interval === null ||
        interval.dueDate < range.dateFrom ||
        interval.startDate > range.dateTo
    ) {
        return null;
    }
    const visibleStart = interval.startDate < range.dateFrom ? range.dateFrom : interval.startDate;
    const visibleEnd = interval.dueDate > range.dateTo ? range.dateTo : interval.dueDate;
    return {
        left: calendarDaysBetween(range.dateFrom, visibleStart) * dayWidth,
        width: (calendarDaysBetween(visibleStart, visibleEnd) + 1) * dayWidth,
        clippedStart: interval.startDate < range.dateFrom,
        clippedEnd: interval.dueDate > range.dateTo,
        openEnd: interval.openEnd,
    };
}

export function timelineDependencyGeometry(
    fromX: number,
    fromY: number,
    toX: number,
    toY: number,
): TimelineDependencyGeometry {
    const bendX =
        fromX <= toX ? fromX + Math.max((toX - fromX) / 2, 8) : Math.max(fromX, toX) + 14;
    return {
        fromX,
        fromY,
        toX,
        toY,
        path: `M ${fromX} ${fromY} H ${bendX} V ${toY} H ${toX}`,
    };
}

export function calendarTaskDragId(taskId: number): string {
    return `calendar-task:${taskId}`;
}

export function calendarDateDropId(date: string): string {
    return `calendar-day:${date}`;
}

/** День на шкале: свой id, чтобы в виде «Рядом» не совпасть с тем же днём сетки. */
export function timelineDateDropId(date: string): string {
    return `calendar-day:tl:${date}`;
}

export function isTimelineDropId(value: string | number): boolean {
    return String(value).startsWith("calendar-day:tl:");
}

export function dateFromDropId(value: string | number): string | null {
    const match = /^calendar-day:(?:tl:)?(\d{4}-\d{2}-\d{2})$/.exec(String(value));
    return match?.[1] ?? null;
}

export function calendarRange(month: string, today = localToday()) {
    const days = buildMonthGrid(month, today);
    return { dateFrom: days[0].date, dateTo: days.at(-1)?.date ?? days[0].date };
}
