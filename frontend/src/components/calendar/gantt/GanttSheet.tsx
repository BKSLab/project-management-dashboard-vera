import { forwardRef, useMemo } from "react";
import { TimelineGrid } from "@/components/calendar/TimelineGrid";
import { TimelineLegend } from "@/components/calendar/gantt/TimelineLegend";
import { buildTimelineDays, type TimelineRange, type TimelineScale } from "@/lib/calendar";
import type { ColorMode } from "@/lib/calendarGrid";
import type { GanttColumn } from "@/lib/ganttView";
import type { TimelineGroupBy } from "@/lib/timelineGroups";
import type { ProjectCalendar } from "@/lib/types";
import { useHolidays } from "@/lib/useCalendarView";

interface GanttSheetProps {
    projectName: string;
    range: TimelineRange;
    scale: TimelineScale;
    data: ProjectCalendar;
    colorMode: ColorMode;
    columns: GanttColumn[];
    labelWidth: number;
    today: string;
    /** Своя ширина дня — режим показа растягивает шкалу на экран. */
    dayWidth?: number;
    groupBy?: TimelineGroupBy;
    onOpenTask?: (taskId: number) => void;
}

const noop = () => undefined;
const DATE = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });

function ruDate(value: string): string {
    return DATE.format(new Date(`${value}T00:00:00`));
}

/**
 * Лист Ганта для показа и выгрузки: шапка (проект, период, дата выгрузки), шкала в натуральную
 * ширину без ручек и кнопок, легенда. Одна и та же разметка — на экране «Режим показа» и в PNG/PDF.
 */
export const GanttSheet = forwardRef<HTMLDivElement, GanttSheetProps>(function GanttSheet(
    { projectName, range, scale, data, colorMode, columns, labelWidth, today, dayWidth, groupBy = "wbs", onOpenTask },
    ref,
) {
    const { holidays } = useHolidays(range);
    const days = useMemo(() => buildTimelineDays(range, today, holidays), [holidays, range, today]);
    const stagesById = useMemo(() => new Map(data.stages.map((stage) => [stage.id, stage])), [data.stages]);
    return (
        <div ref={ref} className="flex w-max flex-col gap-2 bg-surface p-4" data-gantt-sheet="">
            <header className="flex items-baseline justify-between gap-6 px-1">
                <h1 className="text-[18px] font-semibold tracking-[-0.02em] text-primary">{projectName}</h1>
                <p className="text-[12px] text-muted">
                    Гант · {ruDate(range.dateFrom)} — {ruDate(range.dateTo)} · по состоянию на {ruDate(today)}
                </p>
            </header>
            <TimelineGrid
                days={days}
                range={range}
                scale={scale}
                tasks={data.tasks}
                wbsNodes={data.wbs_nodes}
                groupBy={groupBy}
                stagesById={stagesById}
                milestones={data.milestones}
                dependencies={data.dependencies}
                scenarioChanges={[]}
                selectedDate=""
                onSelectDate={noop}
                onOpenTask={onOpenTask ?? noop}
                onScheduleTask={noop}
                onResizeTask={noop}
                colorMode={colorMode}
                columns={columns}
                labelWidth={labelWidth}
                dayWidth={dayWidth}
                staticLayout
            />
            <TimelineLegend mode={colorMode} tasks={data.tasks} stagesById={stagesById} />
        </div>
    );
});
