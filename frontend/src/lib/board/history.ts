/**
 * Стек отмены доски. Запись — снимки затронутых объектов «до» и «после»
 * (null — объекта нет). Отмена применяет «до», повтор — «после».
 * Хранит не больше limit шагов; новая запись сбрасывает ветку повтора.
 */
export interface HistoryEntry<T> {
    before: Map<string, T | null>;
    after: Map<string, T | null>;
}

export class BoardHistory<T> {
    private undoStack: HistoryEntry<T>[] = [];
    private redoStack: HistoryEntry<T>[] = [];
    private readonly limit: number;

    constructor(limit = 100) {
        this.limit = limit;
    }

    push(entry: HistoryEntry<T>): void {
        if (entry.before.size === 0 && entry.after.size === 0) return;
        this.undoStack.push(entry);
        if (this.undoStack.length > this.limit) this.undoStack.shift();
        this.redoStack = [];
    }

    /** Отдаёт снимки, которые надо применить, и переносит запись в стек повтора. */
    undo(): Map<string, T | null> | null {
        const entry = this.undoStack.pop();
        if (!entry) return null;
        this.redoStack.push(entry);
        return entry.before;
    }

    redo(): Map<string, T | null> | null {
        const entry = this.redoStack.pop();
        if (!entry) return null;
        this.undoStack.push(entry);
        return entry.after;
    }

    get canUndo(): boolean {
        return this.undoStack.length > 0;
    }

    get canRedo(): boolean {
        return this.redoStack.length > 0;
    }

    get size(): number {
        return this.undoStack.length;
    }

    /**
     * Забыть объекты, которые ушли мимо истории (заменены на стикер, удалены диалогом):
     * иначе отмена «воскресит» их. Пустые записи выбрасываются.
     */
    forget(keys: Iterable<string>): void {
        const drop = new Set(keys);
        if (drop.size === 0) return;
        const prune = (stack: HistoryEntry<T>[]) =>
            stack
                .map((entry) => {
                    for (const key of drop) {
                        entry.before.delete(key);
                        entry.after.delete(key);
                    }
                    return entry;
                })
                .filter((entry) => entry.before.size > 0 || entry.after.size > 0);
        this.undoStack = prune(this.undoStack);
        this.redoStack = prune(this.redoStack);
    }

    clear(): void {
        this.undoStack = [];
        this.redoStack = [];
    }
}
