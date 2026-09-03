import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "@xyflow/react";
import { X } from "lucide-react";
import {
    DEPENDENCY_COLOR,
    EDGE_ACCENT_COLOR,
    EDGE_ACCENT_WIDTH,
    EDGE_COLOR,
    EDGE_WIDTH,
} from "@/components/wbs/edges/edgeStyle";

/**
 * Связь, которую пользователь провёл сам:
 *
 * * `attachment` — «раздел → задача», то есть привязка задачи к структуре;
 * * `dependency` — «задача → задача», то есть последовательность работ.
 */
export type LinkEdgeTone = "attachment" | "dependency";

export interface LinkEdgeData {
    tone: LinkEdgeTone;
    /** Связь предложена ИИ и ещё не сохранена. */
    isDraft: boolean;
    /** Связь лежит на пути к выделенной задаче и подсвечивается вместе с ним. */
    isOnSelectedPath: boolean;
    removeLabel: string;
    onRemove: () => void;
}

/**
 * Выделенная связь показывает крестик: разорвать её — то же самое, что убрать
 * задачу из раздела или отменить последовательность, и делать это нужно там
 * же, где связь видно.
 */
export function LinkEdge({
    id,
    markerEnd,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    selected,
    data,
}: EdgeProps) {
    const { tone, isDraft, isOnSelectedPath, removeLabel, onRemove } =
        data as unknown as LinkEdgeData;
    const isAccented = selected === true || isOnSelectedPath;
    const baseColor = tone === "dependency" ? DEPENDENCY_COLOR : EDGE_COLOR;
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
                    stroke: isAccented ? EDGE_ACCENT_COLOR : baseColor,
                    strokeWidth: isAccented ? EDGE_ACCENT_WIDTH : EDGE_WIDTH,
                    strokeDasharray: isDraft ? "5 4" : undefined,
                    opacity: 1,
                }}
                markerEnd={markerEnd}
            />
            {selected === true && !isDraft && (
                <EdgeLabelRenderer>
                    <button
                        type="button"
                        aria-label={removeLabel}
                        onClick={onRemove}
                        style={{
                            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
                        }}
                        className="nodrag nopan pointer-events-auto absolute grid size-4 place-items-center rounded-full border border-line-strong bg-surface-2 text-muted hover:border-danger hover:text-danger"
                    >
                        <X size={9} aria-hidden="true" />
                    </button>
                </EdgeLabelRenderer>
            )}
        </>
    );
}
