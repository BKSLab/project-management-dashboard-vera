/**
 * Загрузка команды проекта на шкале: типы ответа GET /projects/{id}/calendar/workload
 * и подписи к ним. Числа и ступени считает бэк (backend/src/utils/workload.py,
 * docs/calendar.md «Загрузка») — здесь только представление, без пересчёта.
 */
import { plural } from "@/lib/plural";

export type WorkloadLevel = 0 | 1 | 2 | 3;

export interface WorkloadDay {
    date: string;
    project_tasks: number;
    project_keys: string[];
    other_tasks: number;
    /** Ключи задач вне проекта, которые смотрящему видны; остальные — только счётчиком. */
    other_keys: string[];
    level: WorkloadLevel;
}

export interface WorkloadOtherTask {
    key: string;
    title: string;
    source_name: string;
    start_date: string | null;
    due_date: string | null;
}

export interface WorkloadPerson {
    user_id: number;
    /** Совпадает с полем assignee задач календаря. */
    name: string;
    days: WorkloadDay[];
    other_tasks: WorkloadOtherTask[];
    other_hidden: number;
}

export interface ProjectWorkload {
    date_from: string;
    date_to: string;
    people: WorkloadPerson[];
    truncated: boolean;
}

export const WORKLOAD_LEVEL_LABELS: Record<WorkloadLevel, string> = {
    0: "свободен",
    1: "норма",
    2: "плотно",
    3: "перегруз",
};

/** Подсказка к легенде и тепловой полосе — одна на весь экран. */
export const WORKLOAD_LEGEND_HINT =
    "Загрузка по рабочим дням: 1 одновременная задача — норма, 2 — плотно, 3 и более — перегруз. Серая полоска снизу — задачи вне проекта.";

function keysLine(keys: string[], limit = 6): string {
    if (keys.length <= limit) return keys.join(", ");
    return `${keys.slice(0, limit).join(", ")} и ещё ${keys.length - limit}`;
}

/** Текст подсказки дня: «N задач: KEY1, KEY2…» с разбивкой на этот проект и другие. */
export function workloadDayHint(day: WorkloadDay): string {
    const total = day.project_tasks + day.other_tasks;
    const head = `${day.date}: ${total} ${plural(total, "задача", "задачи", "задач")} — ${WORKLOAD_LEVEL_LABELS[day.level]}`;
    const lines = [head];
    if (day.project_keys.length > 0) lines.push(`В проекте: ${keysLine(day.project_keys)}`);
    if (day.other_tasks > 0) {
        const hidden = day.other_tasks - day.other_keys.length;
        const parts = [
            day.other_keys.length > 0 ? keysLine(day.other_keys) : null,
            hidden > 0 ? `${hidden} без доступа к проекту` : null,
        ].filter(Boolean);
        lines.push(`В других проектах: ${parts.join(", ")}`);
    }
    return lines.join("\n");
}

export interface WorkloadSummary {
    /** Задач человека на шкале проекта (видимых с учётом фильтров). */
    tasks: number;
    /** Рабочих дней с задачами этого проекта. */
    busyDays: number;
    /** Дней перегруза с учётом других проектов. */
    overloadDays: number;
    /** Дней с задачами в других проектах. */
    otherDays: number;
}

export function workloadSummary(person: WorkloadPerson | undefined, taskCount: number): WorkloadSummary {
    const days = person?.days ?? [];
    return {
        tasks: taskCount,
        busyDays: days.filter((day) => day.project_tasks > 0).length,
        overloadDays: days.filter((day) => day.level === 3).length,
        otherDays: days.filter((day) => day.other_tasks > 0).length,
    };
}

/** Короткая сводка в заголовке строки исполнителя и её развёрнутая подсказка. */
export function workloadSummaryText(summary: WorkloadSummary): { short: string; title: string } {
    // Коротко — чтобы в узкой колонке осталось место для имени; полностью — в подсказке.
    const parts = [String(summary.tasks)];
    parts.push(`${summary.busyDays} дн.`);
    const title = [
        `В периоде: ${summary.tasks} ${plural(summary.tasks, "задача", "задачи", "задач")} в проекте, занят ${summary.busyDays} раб. дн.`,
        summary.otherDays > 0 ? `Задачи в других проектах — ${summary.otherDays} дн.` : null,
        summary.overloadDays > 0 ? `Перегруз — ${summary.overloadDays} дн.` : null,
    ]
        .filter(Boolean)
        .join("\n");
    return { short: parts.join(" · "), title };
}
