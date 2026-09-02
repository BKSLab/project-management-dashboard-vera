import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { Button, IconButton } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import type { TimelineScale } from "@/lib/calendar";

interface CalendarToolbarProps {
    title: string;
    onToday: () => void;
    onPrevious: () => void;
    onNext: () => void;
    scale: TimelineScale;
    onScaleChange: (scale: TimelineScale) => void;
}

export function CalendarToolbar({
    title,
    onToday,
    onPrevious,
    onNext,
    scale,
    onScaleChange,
}: CalendarToolbarProps) {
    const scales: Array<{ value: TimelineScale; label: string }> = [
        { value: "week", label: "Неделя" },
        { value: "month", label: "Месяц" },
        { value: "quarter", label: "Квартал" },
    ];
    return (
        <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Button size="sm" icon={<CalendarDays size={14} />} onClick={onToday}>
                Сегодня
            </Button>
            <div className="flex items-center rounded-md border border-line bg-surface-2">
                <IconButton label="Предыдущий период" size="sm" onClick={onPrevious}>
                    <ChevronLeft size={14} aria-hidden="true" />
                </IconButton>
                <IconButton label="Следующий период" size="sm" onClick={onNext}>
                    <ChevronRight size={14} aria-hidden="true" />
                </IconButton>
            </div>
            <h2 className="min-w-44 text-sm font-semibold text-primary">{title}</h2>
            <div className="flex rounded-md border border-line bg-surface-2 p-0.5" aria-label="Масштаб временной карты">
                {scales.map((item) => (
                    <button
                        key={item.value}
                        type="button"
                        aria-pressed={scale === item.value}
                        onClick={() => onScaleChange(item.value)}
                        className={cn(
                            "h-6 rounded px-2 text-[10px] transition-colors",
                            scale === item.value
                                ? "bg-elevated text-primary shadow-card"
                                : "text-muted hover:text-primary",
                        )}
                    >
                        {item.label}
                    </button>
                ))}
            </div>
        </div>
    );
}
