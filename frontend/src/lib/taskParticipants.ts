import type { Task, TaskParticipantRole } from "@/lib/types";

export function participantUserId(
    task: Task,
    role: Exclude<TaskParticipantRole, "OBSERVER">,
): number | null {
    return (task.participants ?? []).find((participant) => participant.role === role)?.user.id ?? null;
}

export function observerUserIds(task: Task): number[] {
    return (task.participants ?? [])
        .filter((participant) => participant.role === "OBSERVER")
        .map((participant) => participant.user.id);
}
