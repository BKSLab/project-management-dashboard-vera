import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "@xyflow/react";
import { X } from "lucide-react";

export interface AttachmentEdgeData {
    taskId: number;
    isDraft: boolean;
    /** Связь лежит на пути к выделенной задаче и подсвечивается вместе с ним. */
    isOnSelectedPath: boolean;
    onDetach: (taskId: number) => void;
}

/**
 * Стрелка «раздел → задача»: именно она и означает привязку задачи к разделу.
 *
 * Выделенная стрелка показывает крестик: разорвать связь — то же самое, что
 * убрать задачу из структуры, и делать это нужно там же, где связь видно.
 */
export function AttachmentEdge({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    selected,
    data,
}: EdgeProps) {
    const { taskId, isDraft, isOnSelectedPath, onDetach } = data as unknown as AttachmentEdgeData;
    const isAccented = selected === true || isOnSelectedPath;
    const [path, labelX, labelY] = getSmoothStepPath({
        sourceX,
        sourceY,
        targetX,
        targetY,
        sourcePosition,
        targetPosition,
        borderRadius: 8,
    });

    return (
        <>
            <BaseEdge
                id={id}
                path={path}
                style={{
                    stroke: isAccented ? "var(--color-accent)" : "var(--color-border-strong)",
                    strokeWidth: isAccented ? 1.6 : 1,
                    strokeDasharray: isDraft ? "4 3" : undefined,
                    opacity: isAccented ? 0.85 : 0.5,
                }}
            />
            {selected === true && !isDraft && (
                <EdgeLabelRenderer>
                    <button
                        type="button"
                        aria-label="Убрать задачу из раздела"
                        onClick={() => onDetach(taskId)}
                        style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
                        className="nodrag nopan pointer-events-auto absolute grid size-4 place-items-center rounded-full border border-line-strong bg-surface-2 text-muted hover:border-danger hover:text-danger"
                    >
                        <X size={9} aria-hidden="true" />
                    </button>
                </EdgeLabelRenderer>
            )}
        </>
    );
}
