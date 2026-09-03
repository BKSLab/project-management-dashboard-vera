import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/cn";
import type { ProjectStage, TaskCompact } from "@/lib/types";
import { TaskCard } from "@/components/wbs/nodes/TaskCard";

export interface TaskNodeData {
    task: TaskCompact;
    stage: ProjectStage | undefined;
    detail: "full" | "compact" | "minimal";
    /** Карточка лежит на холсте и ещё не связана с разделом. */
    isFloating: boolean;
    /** Карточка входит в предложенную ИИ структуру и пока не сохранена. */
    isDraft: boolean;
    /** От раздела сейчас тянут стрелку: карточка ждёт, что связь бросят в неё. */
    isConnecting: boolean;
    onContextMenu: (taskId: number, anchor: { x: number; y: number }) => void;
}

/**
 * Узел графа для задачи: сама карточка плюс точки связи.
 *
 * Клик открывает панель задачи — его обрабатывает canvas, чтобы отличить клик
 * от перетаскивания.
 */
export function TaskNode({ data, selected }: NodeProps) {
    const { task, stage, detail, isFloating, isDraft, isConnecting, onContextMenu } =
        data as unknown as TaskNodeData;

    return (
        <TaskCard
            task={task}
            stage={stage}
            detail={detail}
            isFloating={isFloating}
            isDraft={isDraft}
            isConnecting={isConnecting}
            isSelected={selected === true}
            onContextMenu={onContextMenu}
        >
            {/* Концы стрелки: сверху в вертикальной раскладке, слева в горизонтальной. */}
            <Handle
                type="target"
                id="top"
                position={Position.Top}
                isConnectableStart={false}
                className="!size-1.5 !border-0 !bg-accent !opacity-0"
            />
            <Handle
                type="target"
                id="left"
                position={Position.Left}
                isConnectableStart={false}
                className="!size-1.5 !border-0 !bg-accent !opacity-0"
            />
            {/*
             * Из этой точки тянут последовательность: стрелка «задача → задача»
             * означает, что вторая работа начинается после первой. Структура и
             * очерёдность — разные вещи, поэтому и точки разные.
             */}
            <Handle
                type="source"
                id="right"
                position={Position.Right}
                isConnectableEnd={false}
                title="Потяните к следующей задаче, чтобы задать очерёдность"
                className={cn(
                    "!size-3 !cursor-crosshair !border-2 !border-surface-2 !bg-[var(--color-warning)]",
                    "transition-[opacity,transform] duration-[var(--duration-fast)]",
                    isDraft ? "!opacity-0" : "!opacity-85 hover:!scale-125 hover:!opacity-100",
                )}
            />
            {/*
             * Поймать связь должна вся карточка, а не точка на её краю: попасть
             * мышью в шестипиксельный кружок невозможно, и промах выглядит так,
             * будто стрелка исчезла. Указатель этот handle не перехватывает —
             * иначе React Flow пометил бы карточку как nodrag и её нельзя было
             * бы таскать; связь притягивается к нему геометрически.
             */}
            <Handle
                type="target"
                id="card"
                position={Position.Left}
                isConnectableStart={false}
                style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    transform: "none",
                    minWidth: 0,
                    minHeight: 0,
                    border: 0,
                    borderRadius: "var(--radius-control)",
                    background: "transparent",
                    pointerEvents: "none",
                }}
            />
        </TaskCard>
    );
}
