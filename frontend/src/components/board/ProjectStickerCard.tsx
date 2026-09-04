import { Link2, Pencil, Trash2 } from "lucide-react";
import type { Node, NodeProps } from "@xyflow/react";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/dates";
import type { ProjectSticker } from "@/lib/board/stickers";
import type { ProjectMember, Task } from "@/lib/types";
import { IconButton } from "@/components/ui/Button";
import { ProjectStickerAuthor } from "@/components/board/ProjectStickerAuthor";

export interface ProjectStickerNodeData extends Record<string, unknown> {
    projectId: number;
    sticker: ProjectSticker;
    members: ProjectMember[];
    tasksById: Map<number, Task>;
    onEdit: (sticker: ProjectSticker) => void;
    onDelete: (sticker: ProjectSticker) => void;
    onOpenTask: (taskId: number) => void;
}

export type ProjectStickerCanvasNode = Node<ProjectStickerNodeData, "sticker">;

export function ProjectStickerCard({
    projectId,
    sticker,
    members,
    tasksById,
    onEdit,
    onDelete,
    onOpenTask,
}: ProjectStickerNodeData) {
    const edited = sticker.updated_at !== sticker.created_at;

    return (
        <article
            className={cn("project-sticker-card", `project-sticker-card--${sticker.color}`)}
            aria-label={`Стикер: ${sticker.body.slice(0, 80)}`}
            title="Перетащите стикер за свободную область карточки"
        >
            <div className="project-sticker-card__tape" aria-hidden="true" />
            <p className="project-sticker-card__body nowheel scrollbar-thin">{sticker.body}</p>

            {sticker.task_ids.length > 0 && (
                <div
                    className="project-sticker-card__tasks nowheel nodrag"
                    aria-label="Связанные задачи"
                >
                    {sticker.task_ids.map((taskId) => {
                        const task = tasksById.get(taskId);
                        return (
                            <button
                                key={taskId}
                                type="button"
                                className="project-sticker-task nodrag nopan"
                                title={task ? `${task.key} · ${task.title}` : `Задача #${taskId}`}
                                onClick={() => onOpenTask(taskId)}
                            >
                                <Link2 size={11} aria-hidden="true" />
                                <span>{task?.key ?? `#${taskId}`}</span>
                            </button>
                        );
                    })}
                </div>
            )}

            <footer className="project-sticker-card__footer">
                <ProjectStickerAuthor
                    projectId={projectId}
                    sticker={sticker}
                    members={members}
                />
                <div className="project-sticker-card__meta">
                    <span title={formatDateTime(sticker.updated_at)}>
                        {formatDateTime(sticker.updated_at)}{edited ? " · изм." : ""}
                    </span>
                    <div className="project-sticker-card__actions">
                        <IconButton
                            size="sm"
                            label="Изменить стикер"
                            className="project-sticker-action nodrag nopan"
                            onClick={() => onEdit(sticker)}
                        >
                            <Pencil size={13} aria-hidden="true" />
                        </IconButton>
                        <IconButton
                            size="sm"
                            label="Удалить стикер"
                            variant="destructive"
                            className="project-sticker-action project-sticker-action--danger nodrag nopan"
                            onClick={() => onDelete(sticker)}
                        >
                            <Trash2 size={13} aria-hidden="true" />
                        </IconButton>
                    </div>
                </div>
            </footer>
        </article>
    );
}

/** Типизированный React Flow node без handles и связей. */
export function ProjectStickerNode({ data }: NodeProps<ProjectStickerCanvasNode>) {
    return <ProjectStickerCard {...data} />;
}
