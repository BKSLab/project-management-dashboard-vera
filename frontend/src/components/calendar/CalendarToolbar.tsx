import type { ReactNode } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, GanttChartSquare, LayoutGrid, Rows2 } from "lucide-react";
import { Button, IconButton } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import type { CalendarViewMode } from "@/lib/calendarGrid";

interface ScaleOption<T extends string> {
    value: T;
    label: string;
    hotkey: string;
}

interface CalendarToolbarProps<T extends string> {
    title: string;
    onToday: () => void;
    onPrevious: () => void;
    onNext: () => void;
    scale: T;
    scales: ScaleOption<T>[];
    onScaleChange: (scale: T) => void;
    /** Переключатель «Сетка | Шкала»; нет — вид один. */
    view?: CalendarViewMode;
    onViewChange?: (view: CalendarViewMode) => void;
    /** Показать вариант «Рядом» (сетка + шкала): только на широком экране. */
    allowSplit?: boolean;
    /** Второй масштаб рядом с первым — в «Рядом» это масштаб шкалы. */
    extraScale?: ReactNode;
    /** Кнопки справа: фильтры, цвет, панель. */
    children?: ReactNode;
}

export function Segmented<T extends string>({
    label,
    value,
    options,
    onChange,
}: {
    label: string;
    value: T;
    options: { value: T; label: ReactNode; title: string }[];
    onChange: (value: T) => void;
}) {
    return (
        <div className="material-metal flex rounded-[var(--radius-control)] border border-line-subtle p-0.5" role="group" aria-label={label}>
            {options.map((item) => (
                <button
                    key={item.value}
                    type="button"
                    aria-pressed={value === item.value}
                    title={item.title}
                    onClick={() => onChange(item.value)}
                    className={cn(
                        "flex h-6 items-center gap-1 rounded-[5px] px-2 text-[11px] transition-colors",
                        value === item.value ? "bg-elevated text-primary shadow-card" : "text-muted hover:text-primary",
                    )}
                >
                    {item.label}
                </button>
            ))}
        </div>
    );
}

/** Шапка календаря: период, вид, масштаб, листание; подсказки называют горячие клавиши. */
export function CalendarToolbar<T extends string>({
    title,
    onToday,
    onPrevious,
    onNext,
    scale,
    scales,
    onScaleChange,
    view,
    onViewChange,
    allowSplit,
    extraScale,
    children,
}: CalendarToolbarProps<T>) {
    return (
        <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h2 className="min-w-0 text-[15px] font-semibold tracking-[-0.02em] text-primary sm:min-w-44" aria-live="polite">
                {title}
            </h2>
            {view && onViewChange && (
                <Segmented
                    label="Вид календаря"
                    value={view}
                    onChange={onViewChange}
                    options={[
                        { value: "grid", label: <><LayoutGrid size={12} aria-hidden="true" /> Сетка</>, title: "Сетка: день, неделя, месяц, год — задачи в клетках дней" },
                        { value: "timeline", label: <><GanttChartSquare size={12} aria-hidden="true" /> Шкала</>, title: "Шкала (Гант): полосы задач по этапам, зависимости, «Что, если»" },
                        ...(allowSplit
                            ? [{ value: "split" as const, label: <><Rows2 size={12} aria-hidden="true" /> Рядом</>, title: "Рядом: сетка сверху, Гант снизу. Клик по дню в сетке прокручивает шкалу к нему; границу между ними можно тянуть" }]
                            : []),
                    ]}
                />
            )}
            <Segmented
                label="Масштаб"
                value={scale}
                onChange={onScaleChange}
                options={scales.map((item) => ({
                    value: item.value,
                    label: item.label,
                    title: item.hotkey ? `${item.label} — клавиша ${item.hotkey}` : item.label,
                }))}
            />
            {extraScale}
            <Button size="sm" variant="ghost" icon={<CalendarDays size={14} aria-hidden="true" />} onClick={onToday} title="Перейти к сегодняшнему дню — клавиша T / Е">
                Сегодня
            </Button>
            <div className="flex items-center">
                <IconButton label="Предыдущий период" title="Предыдущий период — клавиша ←" size="sm" onClick={onPrevious}>
                    <ChevronLeft size={14} aria-hidden="true" />
                </IconButton>
                <IconButton label="Следующий период" title="Следующий период — клавиша →" size="sm" onClick={onNext}>
                    <ChevronRight size={14} aria-hidden="true" />
                </IconButton>
            </div>
            {children && <div className="ml-auto flex flex-wrap items-center gap-1.5">{children}</div>}
        </div>
    );
}
