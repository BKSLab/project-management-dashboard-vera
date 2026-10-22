import { addDateDays } from "@/lib/calendar";

/**
 * Расчёты шкалы (гантта), связанные с графиком: прогресс, критический путь,
 * протягивание связи и сдвиг последователей. Здесь только чистые функции —
 * их проверяет vitest, а компоненты остаются тонкими.
 */

interface DatedItem {
    id: number;
    start_date: string | null;
    due_date: string | null;
}

interface FsLink {
    predecessor_task_id: number;
    successor_task_id: number;
    lag_days: number;
}

/** Процент для заливки полосы или null, если прогресс неизвестен (чек-листа нет). */
export function barProgress(progress: number | null | undefined): number | null {
    if (progress === null || progress === undefined || Number.isNaN(progress)) return null;
    return Math.min(100, Math.max(0, Math.round(progress)));
}

/** Строка подсказки полосы: «Выполнено N%» или пусто. */
export function progressHint(progress: number | null | undefined): string {
    const value = barProgress(progress);
    return value === null ? "" : `Выполнено ${value}%`;
}

export type CriticalState = "critical" | "dimmed" | null;

/** Подсветка полосы в режиме «Критический путь»; вне режима — null. */
export function criticalState(isCritical: boolean | undefined, enabled: boolean): CriticalState {
    if (!enabled) return null;
    return isCritical ? "critical" : "dimmed";
}

/**
 * Прямые последователи, с которыми у задачи с новым сроком возникнет конфликт FS:
 * последователь начинается раньше, чем «новый срок + лаг». Правило то же, что у
 * сервера (NEGATIVE_SLACK и каскад сценария), чтобы вопрос не расходился с расчётом.
 */
export function conflictingSuccessors(
    taskId: number,
    nextDueDate: string | null,
    dependencies: FsLink[],
    tasksById: Map<number, DatedItem>,
): number[] {
    if (nextDueDate === null) return [];
    return dependencies
        .filter((link) => link.predecessor_task_id === taskId)
        .flatMap((link) => {
            const successor = tasksById.get(link.successor_task_id);
            const start = successor ? (successor.start_date ?? successor.due_date) : null;
            if (!successor || start === null) return [];
            return start < addDateDays(nextDueDate, link.lag_days) ? [successor.id] : [];
        });
}

/** Уже связаны ли задачи (в любую сторону) — повтор протягиванием не отправляем. */
export function isAlreadyLinked(predecessorId: number, successorId: number, dependencies: FsLink[]): boolean {
    return dependencies.some(
        (link) =>
            (link.predecessor_task_id === predecessorId && link.successor_task_id === successorId) ||
            (link.predecessor_task_id === successorId && link.successor_task_id === predecessorId),
    );
}

/** Атрибут полосы, по которому ручка связи находит задачу под указателем. */
export const GANTT_TASK_ATTRIBUTE = "data-gantt-task-id";

/** Задача под точкой экрана (полоса шкалы) или null. */
export function taskIdAtPoint(x: number, y: number, root: Document = document): number | null {
    for (const element of root.elementsFromPoint(x, y)) {
        const holder = element.closest(`[${GANTT_TASK_ATTRIBUTE}]`);
        const value = holder?.getAttribute(GANTT_TASK_ATTRIBUTE);
        if (value) return Number(value);
    }
    return null;
}
