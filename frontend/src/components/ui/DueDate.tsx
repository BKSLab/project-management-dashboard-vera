import { AlertTriangle, CalendarDays } from "lucide-react";
import { cn } from "@/lib/cn";
import { daysUntil, dueTone, formatDayMonth, formatFullDate } from "@/lib/dates";

const TONE_CLASSES = {
    muted: "text-muted",
    warning: "text-warning",
    danger: "text-danger",
} as const;

interface DueDateProps {
    value: string | null;
    isDone?: boolean;
    className?: string;
}

/**
 * Срок задачи. Просрочка обозначается иконкой и подписью, а не заливкой
 * карточки, и никогда не передаётся одним лишь цветом (разделы 9 и 16).
 */
export function DueDate({ value, isDone = false, className }: DueDateProps) {
    if (value === null) {
        return null;
    }
    const tone = dueTone(value, isDone);
    const days = daysUntil(value);
    const isOverdue = tone === "danger";
    const suffix =
        isOverdue && days !== null
            ? ` · просрочено на ${Math.abs(days)} дн`
            : tone === "warning" && days === 0
              ? " · сегодня"
              : "";

    return (
        <span
            className={cn("inline-flex items-center gap-1 text-[11px]", TONE_CLASSES[tone], className)}
            title={`Срок: ${formatFullDate(value)}${isOverdue ? " (просрочен)" : ""}`}
        >
            {isOverdue ? (
                <AlertTriangle size={12} aria-hidden="true" />
            ) : (
                <CalendarDays size={12} aria-hidden="true" />
            )}
            <span className="font-mono">{formatDayMonth(value)}</span>
            {suffix && <span className="sr-only">{suffix}</span>}
        </span>
    );
}
