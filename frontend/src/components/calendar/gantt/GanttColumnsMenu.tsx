import { Settings2 } from "lucide-react";
import { Popover } from "@/components/ui/Popover";
import { GANTT_COLUMNS, type GanttColumn } from "@/lib/ganttView";

/** Шестерёнка в шапке левой колонки шкалы: какие колонки показывать рядом с названием задачи. */
export function GanttColumnsMenu({ value, onChange }: { value: GanttColumn[]; onChange: (columns: GanttColumn[]) => void }) {
    return (
        <Popover
            label="Колонки шкалы"
            align="start"
            width={220}
            triggerClassName="h-6 min-h-0 px-1"
            trigger={<Settings2 size={12} aria-hidden="true" />}
        >
            <p className="mb-2 text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">Колонки</p>
            <div className="flex flex-col gap-1.5">
                {GANTT_COLUMNS.map((column) => (
                    <label key={column.id} className="flex items-center gap-2 text-[12px] text-secondary">
                        <input
                            type="checkbox"
                            checked={value.includes(column.id)}
                            onChange={(event) =>
                                onChange(
                                    event.target.checked
                                        ? GANTT_COLUMNS.map((item) => item.id).filter((id) => id === column.id || value.includes(id))
                                        : value.filter((id) => id !== column.id),
                                )
                            }
                        />
                        {column.label}
                    </label>
                ))}
            </div>
            <p className="mt-2 text-[11px] text-muted">Ширину колонки с названиями меняйте, потянув её правую границу в шапке.</p>
        </Popover>
    );
}
