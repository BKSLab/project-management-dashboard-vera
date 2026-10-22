import type { MyTask, MyTaskRoleFilter, Task, TaskKind, TaskStatus } from "@/lib/types";

export const TASK_STATUS_ORDER: TaskStatus[] = ["NEW", "IN_PROGRESS", "REVIEW", "DONE", "CANCELLED"];
export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
    NEW: "Новая", IN_PROGRESS: "В работе", REVIEW: "На проверке", DONE: "Готово", CANCELLED: "Отменена",
};
export const MY_TASK_ROLES: { value: MyTaskRoleFilter; label: string }[] = [
    { value: "all", label: "Все" }, { value: "doing", label: "Делаю" },
    { value: "assigned", label: "Поручил" }, { value: "watching", label: "Наблюдаю" },
];
export const MY_ROLE_LABELS = { EXECUTOR: "исполнитель", REPORTER: "постановщик", OBSERVER: "наблюдатель" };
export function taskKind(task: Pick<Task, "kind" | "project_id">): TaskKind {
    return task.kind ?? (task.project_id === null ? "PERSONAL" : "PROJECT");
}
export function isClosedStatus(status: TaskStatus | null | undefined): boolean {
    return status === "DONE" || status === "CANCELLED";
}
export function filterMyTasks<T extends Pick<MyTask, "key" | "title" | "context">>(tasks: T[], query: string): T[] {
    const term = query.trim().toLocaleLowerCase();
    return !term ? tasks : tasks.filter(task => `${task.key} ${task.title} ${task.context?.name ?? "разовая"}`.toLocaleLowerCase().includes(term));
}
