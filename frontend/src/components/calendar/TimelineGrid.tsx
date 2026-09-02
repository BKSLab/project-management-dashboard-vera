import { useMemo, useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import { CalendarDays, ChevronDown, ChevronRight, FolderTree } from "lucide-react";
import {
    calendarDateDropId,
    calendarDaysBetween,
    timelineBarGeometry,
    timelineDependencyGeometry,
    type CalendarDayModel,
    type TimelineRange,
    type TimelineScale,
} from "@/lib/calendar";
import { cn } from "@/lib/cn";
import { buildTimelineWbsRows } from "@/lib/timelineWbs";
import type {
    CalendarMilestone,
    CalendarStage,
    CalendarTask,
    CalendarWbsNode,
    ScenarioNormalizedChange,
    TaskDependency,
} from "@/lib/types";
import { TimelineTaskBar } from "@/components/calendar/TimelineTaskBar";
import { IconButton } from "@/components/ui/Button";

const TIMELINE_DAY_WIDTH: Record<TimelineScale, number> = {
    week: 104,
    month: 38,
    quarter: 20,
};

function TimelineDropColumn({
    day,
    width,
    height,
}: {
    day: CalendarDayModel;
    width: number;
    height: number;
}) {
    const { isOver, setNodeRef } = useDroppable({ id: calendarDateDropId(day.date) });
    return (
        <div
            ref={setNodeRef}
            aria-hidden="true"
            className={cn(
                "border-r border-line-subtle",
                day.isWeekend && "bg-surface-2/35",
                isOver && "bg-accent/15 ring-1 ring-inset ring-accent",
            )}
            style={{ width, height }}
        />
    );
}

interface TimelineGridProps {
    days: CalendarDayModel[];
    range: TimelineRange;
    scale: TimelineScale;
    tasks: CalendarTask[];
    wbsNodes: CalendarWbsNode[];
    stagesById: Map<number, CalendarStage>;
    milestones: CalendarMilestone[];
    dependencies: TaskDependency[];
    scenarioChanges: ScenarioNormalizedChange[];
    selectedDate: string;
    onSelectDate: (date: string) => void;
    onOpenTask: (taskId: number) => void;
    onScheduleTask: (task: CalendarTask) => void;
    onResizeTask: (task: CalendarTask, edge: "start" | "end", deltaDays: number) => void;
}

export function TimelineGrid({
    days,
    range,
    scale,
    tasks,
    wbsNodes,
    stagesById,
    milestones,
    dependencies,
    scenarioChanges,
    selectedDate,
    onSelectDate,
    onOpenTask,
    onScheduleTask,
    onResizeTask,
}: TimelineGridProps) {
    const [collapsedIds, setCollapsedIds] = useState<Set<number | "unassigned">>(new Set());
    const rows = useMemo(
        () => buildTimelineWbsRows(wbsNodes, tasks, collapsedIds),
        [collapsedIds, tasks, wbsNodes],
    );
    const dayWidth = TIMELINE_DAY_WIDTH[scale];
    const timelineWidth = days.length * dayWidth;
    const rowHeight = scale === "week" ? 48 : 42;
    const headerHeight = 42;
    const bodyHeight = Math.max(rows.length * rowHeight, 92);
    const scenarioByTaskId = useMemo(
        () => new Map(scenarioChanges.map((change) => [change.task_id, change])),
        [scenarioChanges],
    );
    const dependencyPaths = useMemo(() => {
        const rowByTaskId = new Map<number, number>();
        rows.forEach((row, index) => {
            if (row.kind === "task") rowByTaskId.set(row.task.id, index);
        });
        const taskById = new Map(tasks.map((task) => [task.id, task]));
        return dependencies.flatMap((dependency) => {
            const predecessor = taskById.get(dependency.predecessor_task_id);
            const successor = taskById.get(dependency.successor_task_id);
            const predecessorRow = rowByTaskId.get(dependency.predecessor_task_id);
            const successorRow = rowByTaskId.get(dependency.successor_task_id);
            if (
                predecessor === undefined ||
                successor === undefined ||
                predecessorRow === undefined ||
                successorRow === undefined
            ) {
                return [];
            }
            const predecessorBar = timelineBarGeometry(predecessor, range, dayWidth);
            const successorBar = timelineBarGeometry(successor, range, dayWidth);
            if (predecessorBar === null || successorBar === null) return [];
            return [
                {
                    dependency,
                    geometry: timelineDependencyGeometry(
                        predecessorBar.left + predecessorBar.width,
                        predecessorRow * rowHeight + rowHeight / 2,
                        successorBar.left,
                        successorRow * rowHeight + rowHeight / 2,
                    ),
                    predecessor,
                    successor,
                },
            ];
        });
    }, [dayWidth, dependencies, range, rowHeight, rows, tasks]);

    function toggleRow(id: number | "unassigned") {
        setCollapsedIds((current) => {
            const next = new Set(current);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }

    return (
        <section className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
            <div className="scrollbar-thin overflow-x-auto">
                <div className="relative min-w-max" style={{ width: 210 + timelineWidth }}>
                    <div
                        className="sticky top-0 z-30 grid border-b border-line bg-surface-2/95 backdrop-blur-sm"
                        style={{ gridTemplateColumns: `210px ${timelineWidth}px`, height: headerHeight }}
                    >
                        <div className="sticky left-0 z-40 flex items-center gap-2 border-r border-line bg-surface-2 px-3 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
                            <CalendarDays size={13} /> Работа
                        </div>
                        <div className="flex">
                            {days.map((day, index) => {
                                const showLabel =
                                    scale !== "quarter" || day.dayNumber === 1 || index % 7 === 0;
                                return (
                                    <button
                                        key={day.date}
                                        type="button"
                                        title={day.date}
                                        aria-label={`Открыть agenda за ${day.date}`}
                                        onClick={() => onSelectDate(day.date)}
                                        className={cn(
                                            "shrink-0 border-r border-line-subtle text-[10px] text-muted hover:bg-hover hover:text-primary",
                                            day.isWeekend && "bg-surface-2",
                                            day.isToday && "text-accent",
                                            selectedDate === day.date && "bg-accent/10 text-accent",
                                        )}
                                        style={{ width: dayWidth }}
                                    >
                                        {showLabel ? day.dayNumber : ""}
                                        {scale === "week" && (
                                            <span className="ml-1 hidden text-[9px] uppercase sm:inline">
                                                {new Intl.DateTimeFormat("ru-RU", {
                                                    weekday: "short",
                                                }).format(
                                                    new Date(
                                                        Number(day.date.slice(0, 4)),
                                                        Number(day.date.slice(5, 7)) - 1,
                                                        Number(day.date.slice(8, 10)),
                                                    ),
                                                )}
                                            </span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div className="relative" style={{ minHeight: bodyHeight }}>
                        <div
                            className="pointer-events-none absolute top-0 left-[210px] z-0 flex"
                            style={{ width: timelineWidth, height: bodyHeight }}
                        >
                            {days.map((day) => (
                                <TimelineDropColumn
                                    key={day.date}
                                    day={day}
                                    width={dayWidth}
                                    height={bodyHeight}
                                />
                            ))}
                        </div>
                        {days.map(
                            (day, index) =>
                                day.isToday && (
                                    <div
                                        key={`today-${day.date}`}
                                        aria-label="Сегодня"
                                        className="pointer-events-none absolute top-0 z-20 w-px bg-accent shadow-[0_0_8px_var(--color-accent)]"
                                        style={{
                                            left: 210 + index * dayWidth + dayWidth / 2,
                                            height: bodyHeight,
                                        }}
                                    />
                                ),
                        )}
                        {milestones.map((milestone) => {
                            const offset =
                                calendarDaysBetween(range.dateFrom, milestone.due_date) * dayWidth +
                                dayWidth / 2;
                            return (
                                <div
                                    key={`${milestone.is_system ? "system" : milestone.id}:${milestone.due_date}`}
                                    className={cn(
                                        "pointer-events-none absolute top-0 z-20 border-l border-dashed",
                                        milestone.status === "ACHIEVED"
                                            ? "border-success"
                                            : "border-purple",
                                    )}
                                    style={{ left: 210 + offset, height: bodyHeight }}
                                    title={`${milestone.title} · ${milestone.due_date}`}
                                >
                                    <span
                                        className={cn(
                                            "absolute -top-1.5 -left-1 size-2 rotate-45 border",
                                            milestone.status === "ACHIEVED"
                                                ? "border-success bg-success"
                                                : "border-purple bg-surface",
                                        )}
                                    />
                                    <span className="absolute top-1 left-1 max-w-28 truncate rounded bg-surface-2/90 px-1 py-0.5 text-[9px] text-purple">
                                        ◆ {milestone.title}
                                    </span>
                                </div>
                            );
                        })}
                        {dependencyPaths.length > 0 && (
                            <svg
                                aria-label="Зависимости задач Finish-to-Start"
                                className="pointer-events-none absolute top-0 left-[210px] z-[5] overflow-visible text-accent"
                                width={timelineWidth}
                                height={bodyHeight}
                                viewBox={`0 0 ${timelineWidth} ${bodyHeight}`}
                            >
                                <defs>
                                    <marker
                                        id="timeline-dependency-arrow"
                                        markerWidth="6"
                                        markerHeight="6"
                                        refX="5"
                                        refY="3"
                                        orient="auto"
                                    >
                                        <path d="M 0 0 L 6 3 L 0 6 z" fill="currentColor" />
                                    </marker>
                                </defs>
                                {dependencyPaths.map(
                                    ({ dependency, geometry, predecessor, successor }) => (
                                        <path
                                            key={dependency.id}
                                            d={geometry.path}
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="1.25"
                                            strokeDasharray={
                                                dependency.lag_days > 0 ? "4 3" : undefined
                                            }
                                            markerEnd="url(#timeline-dependency-arrow)"
                                            opacity="0.62"
                                        >
                                            <title>
                                                {predecessor.key} → {successor.key}
                                                {dependency.lag_days > 0
                                                    ? `, задержка ${dependency.lag_days} дн.`
                                                    : ""}
                                            </title>
                                        </path>
                                    ),
                                )}
                            </svg>
                        )}

                        {rows.map((row) => {
                            if (row.kind !== "task") {
                                const aggregateStart = row.aggregate.startDate;
                                const aggregateEnd = row.aggregate.dueDate;
                                const visibleStart =
                                    aggregateStart && aggregateStart < range.dateFrom
                                        ? range.dateFrom
                                        : aggregateStart;
                                const visibleEnd =
                                    aggregateEnd && aggregateEnd > range.dateTo
                                        ? range.dateTo
                                        : aggregateEnd;
                                const left = visibleStart
                                    ? calendarDaysBetween(range.dateFrom, visibleStart) * dayWidth
                                    : 0;
                                const width =
                                    visibleStart && visibleEnd
                                        ? (calendarDaysBetween(visibleStart, visibleEnd) + 1) *
                                          dayWidth
                                        : 0;
                                const collapseKey = row.nodeId ?? "unassigned";
                                return (
                                    <div
                                        key={row.id}
                                        className="relative grid border-b border-line bg-surface-2/55"
                                        style={{
                                            gridTemplateColumns: `210px ${timelineWidth}px`,
                                            height: rowHeight,
                                        }}
                                    >
                                        <button
                                            type="button"
                                            disabled={!row.hasChildren}
                                            aria-expanded={row.hasChildren ? !row.collapsed : undefined}
                                            onClick={() => row.hasChildren && toggleRow(collapseKey)}
                                            className="sticky left-0 z-20 flex min-w-0 items-center gap-1.5 border-r border-line bg-surface-2 px-2 text-left disabled:cursor-default"
                                            style={{ paddingLeft: 8 + row.depth * 14 }}
                                        >
                                            {row.hasChildren ? (
                                                row.collapsed ? (
                                                    <ChevronRight size={13} className="shrink-0" />
                                                ) : (
                                                    <ChevronDown size={13} className="shrink-0" />
                                                )
                                            ) : (
                                                <FolderTree size={12} className="shrink-0 text-muted" />
                                            )}
                                            <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-primary">
                                                {row.number && (
                                                    <span className="mr-1 font-mono text-[10px] text-muted">
                                                        {row.number}
                                                    </span>
                                                )}
                                                {row.title}
                                            </span>
                                            <span className="shrink-0 font-mono text-[9px] text-muted">
                                                {row.aggregate.total} · {row.aggregate.progress}% ·{" "}
                                                {row.aggregate.risks} риск.
                                            </span>
                                        </button>
                                        <div className="relative" style={{ width: timelineWidth }}>
                                            {row.collapsed && width > 0 && (
                                                <div
                                                    className="absolute top-2 h-5 rounded border border-accent-border/60 bg-accent/15 px-2 text-[9px] leading-5 text-accent shadow-card"
                                                    style={{ left, width }}
                                                    title={`${row.title}: ${row.aggregate.total} задач, ${row.aggregate.progress}% завершено, рисков: ${row.aggregate.risks}`}
                                                >
                                                    <span className="block truncate">
                                                        {row.aggregate.total} задач ·{" "}
                                                        {row.aggregate.progress}%
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            }
                            const task = row.task;
                            const geometry = timelineBarGeometry(task, range, dayWidth);
                            const baselineGeometry = task.baseline_due_date
                                ? timelineBarGeometry(
                                      {
                                          ...task,
                                          start_date: task.baseline_start_date,
                                          due_date: task.baseline_due_date,
                                      },
                                      range,
                                      dayWidth,
                                  )
                                : null;
                            const scenarioChange = scenarioByTaskId.get(task.id);
                            const scenarioGeometry = scenarioChange
                                ? timelineBarGeometry(
                                      {
                                          ...task,
                                          start_date: scenarioChange.proposed.start_date,
                                          due_date: scenarioChange.proposed.due_date,
                                      },
                                      range,
                                      dayWidth,
                                  )
                                : null;
                            return (
                                <div
                                    key={row.id}
                                    className="relative grid border-b border-line-subtle last:border-b-0"
                                    style={{
                                        gridTemplateColumns: `210px ${timelineWidth}px`,
                                        height: rowHeight,
                                    }}
                                >
                                    <div
                                        className="sticky left-0 z-20 flex min-w-0 items-center gap-1 border-r border-line bg-surface px-2"
                                        style={{ paddingLeft: 8 + row.depth * 14 }}
                                    >
                                        <button
                                            type="button"
                                            onClick={() => onOpenTask(task.id)}
                                            className="min-w-0 flex-1 truncate text-left text-[11px] text-secondary hover:text-primary"
                                        >
                                            <span className="font-mono text-[10px] text-accent">
                                                {task.key}
                                            </span>{" "}
                                            {task.title}
                                        </button>
                                        {task.drift_days !== null && task.drift_days !== 0 && (
                                            <span
                                                className={cn(
                                                    "shrink-0 font-mono text-[9px]",
                                                    task.drift_days > 0
                                                        ? "text-danger"
                                                        : "text-success",
                                                )}
                                                title={`Отклонение от baseline: ${task.drift_days} дн.`}
                                            >
                                                {task.drift_days > 0 ? "+" : ""}
                                                {task.drift_days}д
                                            </span>
                                        )}
                                        <IconButton
                                            size="sm"
                                            label={`Изменить даты ${task.key}`}
                                            onClick={() => onScheduleTask(task)}
                                        >
                                            <CalendarDays size={11} />
                                        </IconButton>
                                    </div>
                                    <div className="relative" style={{ width: timelineWidth }}>
                                        {baselineGeometry && (
                                            <div
                                                className="absolute bottom-1 z-10 h-1 rounded-full border border-dashed border-line-strong bg-surface-2 opacity-75"
                                                style={{
                                                    left: baselineGeometry.left,
                                                    width: baselineGeometry.width,
                                                }}
                                                title={`Baseline: ${task.baseline_start_date ?? task.baseline_due_date} — ${task.baseline_due_date}`}
                                            />
                                        )}
                                        {geometry && (
                                            <TimelineTaskBar
                                                task={task}
                                                stage={stagesById.get(task.stage_id)}
                                                geometry={geometry}
                                                dayWidth={dayWidth}
                                                scale={scale}
                                                onOpen={onOpenTask}
                                                onResize={onResizeTask}
                                            />
                                        )}
                                        {scenarioGeometry && scenarioChange && (
                                            <div
                                                aria-label={`Предложенный интервал ${task.key}`}
                                                className="pointer-events-none absolute top-1.5 z-[15] flex h-8 items-center overflow-hidden rounded-lg border border-purple/80 px-2 text-[9px] font-semibold text-purple shadow-[0_0_12px_color-mix(in_srgb,var(--color-purple)_25%,transparent)]"
                                                style={{
                                                    left: scenarioGeometry.left,
                                                    width: scenarioGeometry.width,
                                                    backgroundImage:
                                                        "repeating-linear-gradient(135deg, transparent 0 6px, color-mix(in srgb, var(--color-purple) 18%, transparent) 6px 10px)",
                                                }}
                                                title={`PROPOSED · ${scenarioChange.proposed.start_date ?? scenarioChange.proposed.due_date ?? "—"} — ${scenarioChange.proposed.due_date ?? "—"}`}
                                            >
                                                <span className="truncate">PROPOSED</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                        {rows.length === 0 && (
                            <div className="absolute inset-0 left-[210px] flex items-center justify-center text-[12px] text-muted">
                                В этом диапазоне нет запланированных задач
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </section>
    );
}
