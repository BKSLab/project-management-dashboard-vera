import type { ReactNode } from "react";
import { X } from "lucide-react";
import { IconButton } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

export interface SidePanelTab<T extends string> {
    id: T;
    label: string;
    title: string;
    count?: number;
    content: ReactNode;
}

/**
 * Выдвижная панель справа от календаря со вкладками. На широком экране — колонка со своей
 * прокруткой, на телефоне — поверх календаря. Сверху можно положить блок (сценарий «Что, если»).
 */
export function CalendarSidePanel<T extends string>({
    tabs,
    active,
    onActiveChange,
    onClose,
    top,
}: {
    tabs: SidePanelTab<T>[];
    active: T;
    onActiveChange: (tab: T) => void;
    onClose: () => void;
    top?: ReactNode;
}) {
    const current = tabs.find((tab) => tab.id === active) ?? tabs[0];
    return (
        <aside
            aria-label="Панель календаря"
            className={cn(
                "flex min-h-0 flex-col bg-surface",
                "absolute inset-0 z-30 md:static md:z-auto md:w-[340px] md:shrink-0 md:border-l md:border-line",
            )}
        >
            <div className="flex shrink-0 items-center gap-1 border-b border-line px-2 py-1.5">
                <div className="flex min-w-0 flex-1 flex-wrap gap-0.5" role="tablist" aria-label="Разделы панели">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            type="button"
                            role="tab"
                            aria-selected={tab.id === current.id}
                            title={tab.title}
                            onClick={() => onActiveChange(tab.id)}
                            className={cn(
                                "flex h-7 items-center gap-1 rounded-[6px] px-2 text-[12px] transition-colors",
                                tab.id === current.id ? "bg-active font-semibold text-primary" : "text-muted hover:bg-hover hover:text-primary",
                            )}
                        >
                            {tab.label}
                            {tab.count !== undefined && tab.count > 0 && <span className="font-mono text-[10px] text-muted">{tab.count}</span>}
                        </button>
                    ))}
                </div>
                <IconButton size="sm" label="Свернуть панель" title="Свернуть панель — календарь займёт всю ширину" onClick={onClose}>
                    <X size={14} aria-hidden="true" />
                </IconButton>
            </div>
            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-3" role="tabpanel" aria-label={current.label}>
                {top && <div className="mb-3">{top}</div>}
                {current.content}
            </div>
        </aside>
    );
}
