import { CalendarClock } from "lucide-react";
import { dayTitle } from "@/lib/calendar";
import type { CalendarDateChange } from "@/lib/types";

function dateLabel(value: string | null): string {
    return value === null ? "без срока" : dayTitle(value);
}

interface CalendarRecentChangesProps {
    changes: CalendarDateChange[];
    onOpenTask: (taskId: number) => void;
}

export function CalendarRecentChanges({ changes, onOpenTask }: CalendarRecentChangesProps) {
    if (changes.length === 0) return null;

    return (
        <section className="rounded-lg border border-line bg-surface p-3 shadow-card">
            <div className="mb-2 flex items-center gap-2">
                <CalendarClock size={14} className="text-muted" aria-hidden="true" />
                <h3 className="text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
                    Недавние переносы
                </h3>
            </div>
            <div className="flex max-h-52 flex-col gap-1 overflow-y-auto">
                {changes.map((change) => (
                    <button
                        key={change.id}
                        type="button"
                        onClick={() => onOpenTask(change.task_id)}
                        className="rounded-md border border-line-subtle bg-surface-2 px-2 py-1.5 text-left hover:border-line-strong hover:bg-hover"
                    >
                        <span className="block truncate text-[11px] text-primary">
                            <span className="font-mono text-accent">{change.task_key}</span>{" "}
                            {change.task_title}
                        </span>
                        <span className="block truncate text-[10px] text-muted">
                            {dateLabel(change.from_date)} → {dateLabel(change.to_date)}
                        </span>
                    </button>
                ))}
            </div>
        </section>
    );
}
