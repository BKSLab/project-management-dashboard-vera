import type { DashboardTask } from "@/lib/types";
import { formatRelative } from "@/lib/dates";
import { DueDate } from "@/components/ui/DueDate";
import { TaskLine } from "@/components/tasks/TaskLine";

interface TaskRowProps {
    task: DashboardTask;
    /** Вместо срока показывает время последнего изменения. */
    showUpdated?: boolean;
    onOpen: (taskId: number) => void;
}

/** Строка задачи в сводке портфеля: одна сущность — один визуальный язык. */
export function TaskRow({ task, showUpdated = false, onOpen }: TaskRowProps) {
    return (
        <TaskLine
            dotColor={task.project_color}
            taskKey={task.key}
            title={task.title}
            stage={task.stage_name}
            priority={task.priority}
            meta={showUpdated ? formatRelative(task.updated_at) : <DueDate value={task.due_date} />}
            onOpen={() => onOpen(task.id)}
        />
    );
}
