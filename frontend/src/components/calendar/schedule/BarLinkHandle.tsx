import { useState, type PointerEvent as ReactPointerEvent } from "react";
import { createPortal } from "react-dom";
import { taskIdAtPoint } from "@/lib/ganttSchedule";

interface Point {
    x: number;
    y: number;
}

interface BarLinkHandleProps {
    taskKey: string;
    taskId: number;
    /** Отпустили над другой полосой: создать связь «эта → та». */
    onLink: (predecessorId: number, successorId: number) => void;
}

/**
 * Кружок на правом краю полосы: потяните к другой полосе — появится связь
 * «эта задача должна закончиться до начала той» (Finish-to-Start).
 */
export function BarLinkHandle({ taskKey, taskId, onLink }: BarLinkHandleProps) {
    const [line, setLine] = useState<{ from: Point; to: Point } | null>(null);

    function start(event: ReactPointerEvent<HTMLButtonElement>) {
        event.preventDefault();
        event.stopPropagation();
        const rect = event.currentTarget.getBoundingClientRect();
        const from = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
        setLine({ from, to: { x: event.clientX, y: event.clientY } });
        const move = (moveEvent: PointerEvent) =>
            setLine({ from, to: { x: moveEvent.clientX, y: moveEvent.clientY } });
        const stop = (upEvent: PointerEvent) => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", stop);
            window.removeEventListener("pointercancel", cancel);
            setLine(null);
            const target = taskIdAtPoint(upEvent.clientX, upEvent.clientY);
            if (target !== null && target !== taskId) onLink(taskId, target);
        };
        const cancel = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", stop);
            window.removeEventListener("pointercancel", cancel);
            setLine(null);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", stop);
        window.addEventListener("pointercancel", cancel);
    }

    return (
        <>
            <button
                type="button"
                data-link-handle=""
                aria-label={`Связать ${taskKey} со следующей задачей`}
                title={"Потяните к другой полосе — она начнётся после этой задачи.\nСвязь можно удалить на вкладке «Зависимости»."}
                className="absolute top-1/2 -right-3 z-30 size-3 -translate-y-1/2 cursor-crosshair touch-none rounded-full border-2 border-accent bg-surface opacity-0 shadow-card transition-opacity duration-[var(--duration-fast)] group-hover/calendar-task:opacity-100 focus-visible:opacity-100 motion-reduce:transition-none"
                onPointerDown={start}
            />
            {line &&
                createPortal(
                    <svg
                        aria-hidden="true"
                        data-link-preview=""
                        className="pointer-events-none fixed inset-0 z-[100] h-full w-full text-accent"
                    >
                        <line
                            x1={line.from.x}
                            y1={line.from.y}
                            x2={line.to.x}
                            y2={line.to.y}
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeDasharray="4 3"
                        />
                        <circle cx={line.to.x} cy={line.to.y} r="4" fill="currentColor" />
                    </svg>,
                    document.body,
                )}
        </>
    );
}
