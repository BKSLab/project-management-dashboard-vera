import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Project } from "@/lib/types";
import type { WbsProgress } from "@/lib/wbsTree";
import { ProgressBar } from "@/components/ui/Progress";

export interface ProjectNodeData {
    project: Project;
    progress: WbsProgress;
}

/**
 * Корень графа — сам проект (§19 ТЗ). Это не WbsNode: узел добавляется
 * системой, его нельзя переместить или удалить.
 */
export function ProjectNode({ data }: NodeProps) {
    const { project, progress } = data as unknown as ProjectNodeData;
    const percent = progress.total === 0 ? 0 : progress.done / progress.total;

    return (
        <div
            style={{ borderColor: `${project.color}66` }}
            className="material-metal flex h-full w-full flex-col justify-between rounded-[var(--radius-panel)] border px-4 py-3 shadow-elevated"
        >
            <Handle type="source" position={Position.Right} className="!opacity-0" isConnectable={false} />

            <div className="flex min-w-0 items-start gap-2">
                {project.icon ? (
                    <span aria-hidden="true" className="text-base leading-none">
                        {project.icon}
                    </span>
                ) : (
                    <span
                        aria-hidden="true"
                        style={{ backgroundColor: project.color }}
                        className="mt-1.5 size-2 shrink-0 rounded-full"
                    />
                )}
                <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="text-[10px] font-medium tracking-[0.08em] text-muted uppercase">
                        Проект
                    </span>
                    <h2 className="line-clamp-2 text-[14px] leading-snug font-semibold text-primary">
                        {project.name}
                    </h2>
                </div>
            </div>

            <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-[10px]">
                    <span className="text-muted">{progress.total} задач</span>
                    <span className="font-mono text-secondary">{Math.round(percent * 100)}%</span>
                </div>
                <ProgressBar
                    value={percent}
                    color={project.color}
                    label={`Прогресс проекта ${project.name}`}
                    className="h-1"
                />
            </div>
        </div>
    );
}
