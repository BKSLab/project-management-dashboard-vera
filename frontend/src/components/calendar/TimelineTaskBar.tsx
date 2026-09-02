import type { PointerEvent as ReactPointerEvent } from "react";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { AlertTriangle } from "lucide-react";
import { calendarTaskDragId, type TimelineBarGeometry, type TimelineScale } from "@/lib/calendar";
import { cn } from "@/lib/cn";
import type { CalendarStage, CalendarTask } from "@/lib/types";

interface TimelineTaskBarProps {
    task: CalendarTask;
    stage?: CalendarStage;
    geometry: TimelineBarGeometry;
    dayWidth: number;
    scale: TimelineScale;
    onOpen: (taskId: number) => void;
    onResize: (task: CalendarTask, edge: "start" | "end", deltaDays: number) => void;
}

export function TimelineTaskBar({
    task,
    stage,
    geometry,
    dayWidth,
    scale,
    onOpen,
    onResize,
}: TimelineTaskBarProps) {
    const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
        id: calendarTaskDragId(task.id),
        data: { task, dragKind: "interval" },
    });
    const dates = `${task.start_date ?? task.due_date ?? "—"} — ${task.due_date ?? "—"}`;
    const risk = task.risk_reasons.map((reason) => reason.message).join(" · ");

    function startPointerResize(edge: "start" | "end", event: ReactPointerEvent) {
        event.preventDefault();
        event.stopPropagation();
        const startX = event.clientX;
        const finish = (finishEvent: PointerEvent) => {
            const delta = Math.round((finishEvent.clientX - startX) / dayWidth);
            if (delta !== 0) onResize(task, edge, delta);
            window.removeEventListener("pointercancel", cancel);
        };
        const cancel = () => window.removeEventListener("pointerup", finish);
        window.addEventListener("pointerup", finish, { once: true });
        window.addEventListener("pointercancel", cancel, { once: true });
    }

    function resizeFromKeyboard(edge: "start" | "end", key: string) {
        if (key === "ArrowLeft") onResize(task, edge, -1);
        if (key === "ArrowRight") onResize(task, edge, 1);
    }

    return (
        <div
            ref={setNodeRef}
            className={cn(
                "absolute top-1.5 z-10 flex h-8 min-w-6 items-stretch overflow-hidden rounded-lg border shadow-card",
                "transition-[border-color,box-shadow,opacity] duration-[var(--duration-fast)] motion-reduce:transition-none",
                task.is_done && "border-line bg-surface-2 text-muted",
                task.is_overdue && "border-danger/50 bg-danger/15 text-primary",
                !task.is_done && !task.is_overdue && "border-line-strong bg-elevated text-primary",
                isDragging && "opacity-45 shadow-panel",
                geometry.clippedStart && "rounded-l-none border-l-0",
                geometry.clippedEnd && "rounded-r-none border-r-0",
            )}
            style={{
                left: geometry.left,
                width: geometry.width,
                transform: CSS.Translate.toString(transform),
            }}
        >
            <button
                type="button"
                className="min-w-0 flex-1 cursor-grab touch-none px-2 text-left active:cursor-grabbing"
                title={`${task.key} · ${task.title}\n${stage?.name ?? "Стадия не найдена"} · ${dates}${risk ? `\n${risk}` : ""}`}
                aria-label={`Переместить интервал ${task.key}: ${task.title}. ${dates}`}
                onClick={() => onOpen(task.id)}
                {...attributes}
                {...listeners}
            >
                <span className="flex min-w-0 items-center gap-1.5">
                    {task.risk_level && <AlertTriangle size={11} className="shrink-0" />}
                    <span className="shrink-0 font-mono text-[10px]">{task.key}</span>
                    {scale !== "quarter" && (
                        <span className="truncate text-[11px]">{task.title}</span>
                    )}
                    {scale === "week" && (
                        <span className="ml-auto shrink-0 text-[9px] text-muted">
                            {dates}
                        </span>
                    )}
                </span>
            </button>
            {task.start_date !== null && (
                <button
                    type="button"
                    aria-label={`Изменить начало ${task.key}. Стрелки влево и вправо меняют дату на день`}
                    title="Потяните, чтобы изменить начало"
                    className="absolute inset-y-0 left-0 w-2 cursor-ew-resize border-l-2 border-transparent hover:border-accent focus-visible:border-accent"
                    onPointerDown={(event) => startPointerResize("start", event)}
                    onKeyDown={(event) => {
                        if (event.key.startsWith("Arrow")) event.preventDefault();
                        resizeFromKeyboard("start", event.key);
                    }}
                />
            )}
            <button
                type="button"
                aria-label={`Изменить завершение ${task.key}. Стрелки влево и вправо меняют дату на день`}
                title="Потяните, чтобы изменить завершение"
                className="absolute inset-y-0 right-0 w-2 cursor-ew-resize border-r-2 border-transparent hover:border-accent focus-visible:border-accent"
                onPointerDown={(event) => startPointerResize("end", event)}
                onKeyDown={(event) => {
                    if (event.key.startsWith("Arrow")) event.preventDefault();
                    resizeFromKeyboard("end", event.key);
                }}
            />
        </div>
    );
}
