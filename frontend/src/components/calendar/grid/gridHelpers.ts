/** Вспомогательные функции сетки календаря (без React-компонентов — для быстрой перезагрузки). */
import type { MouseEvent } from "react";
import { useDroppable } from "@dnd-kit/core";
import { calendarDateDropId } from "@/lib/calendar";
import { isMultiDay, singleDayDate, taskSpan } from "@/lib/calendarGrid";
import type { CalendarGridMilestone, CalendarGridTask } from "@/lib/types";

export function byImportance(first: CalendarGridTask, second: CalendarGridTask): number {
    return (
        Number(first.is_done) - Number(second.is_done) ||
        Number(second.is_overdue) - Number(first.is_overdue) ||
        first.key.localeCompare(second.key)
    );
}

export function groupSingles(tasks: CalendarGridTask[]) {
    const map = new Map<string, CalendarGridTask[]>();
    for (const task of tasks) {
        if (isMultiDay(task)) continue;
        const date = singleDayDate(task);
        if (date === null) continue;
        const bucket = map.get(date) ?? [];
        bucket.push(task);
        map.set(date, bucket);
    }
    for (const bucket of map.values()) bucket.sort(byImportance);
    return map;
}

export function groupMilestones(milestones: CalendarGridMilestone[]) {
    const map = new Map<string, CalendarGridMilestone[]>();
    for (const milestone of milestones) {
        const bucket = map.get(milestone.due_date) ?? [];
        bucket.push(milestone);
        map.set(milestone.due_date, bucket);
    }
    return map;
}

/** Клик по пустому месту дня создаёт задачу, а не по карточке/кнопке внутри. */
export function isEmptySpotClick(event: MouseEvent): boolean {
    return !(event.target as Element).closest("[data-grid-item], button, a");
}

/** Доля фирменного цвета на ступень тепловой шкалы; смесь с фоном — только токены. */
const HEAT_MIX = [0, 22, 45, 70, 100];

export function heatStyle(level: number) {
    if (level === 0) return undefined;
    return {
        background: `color-mix(in srgb, var(--color-accent) ${HEAT_MIX[level]}%, var(--color-bg-surface))`,
        color: level >= 3 ? "var(--color-text-on-accent)" : undefined,
    };
}


export const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

export const ITEM_HEIGHT = 20;

const DATE_SHORT = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });

export function shortDate(value: string): string {
    const [year, month, day] = value.split("-").map(Number);
    return DATE_SHORT.format(new Date(year, month - 1, day));
}

export function stateLabel(task: CalendarGridTask): string {
    if (task.is_done) return "выполнена";
    if (task.is_overdue) return "просрочена";
    if (task.is_due_soon) return "срок близко";
    return "в плане";
}

export function taskTooltip(task: CalendarGridTask, stageName?: string): string {
    const span = taskSpan(task);
    const dates =
        span === null
            ? "без срока"
            : span.start === span.end
              ? `срок ${shortDate(span.end)}`
              : `${shortDate(span.start)} — ${shortDate(span.end)}`;
    const place = task.source ? `${task.source.key ?? ""} ${task.source.name}`.trim() : stageName;
    return [
        `${task.key} · ${task.title}`,
        [dates, stateLabel(task), task.assignee ?? "без исполнителя"].join(" · "),
        place,
        "Клик — открыть карточку; перетащите на другой день, чтобы перенести срок",
    ]
        .filter(Boolean)
        .join("\n");
}

export function milestoneTooltip(milestone: CalendarGridMilestone): string {
    const status = milestone.status === "ACHIEVED" ? "достигнута" : "запланирована";
    const project = milestone.project ? `\n${milestone.project.key} · ${milestone.project.name}` : "";
    return `Веха «${milestone.title}» · ${shortDate(milestone.due_date)} · ${status}${project}`;
}

/** Клетка-приёмник перетаскивания: карточку можно бросить на этот день. */
export function useDayDrop(date: string) {
    return useDroppable({ id: calendarDateDropId(date) });
}


/**
 * День, за который взяли полосу многодневной задачи: пишется при нажатии указателя, читается
 * при отпускании. С клавиатуры нажатия нет — тогда берётся день из данных карточки.
 */
const gridGrab = { id: "", date: "" };

export function rememberGridGrab(id: string, date: string) {
    gridGrab.id = id;
    gridGrab.date = date;
}

export function gridGrabDate(activeId: string | number, fallback: string): string {
    return gridGrab.id === String(activeId) ? gridGrab.date : fallback;
}
