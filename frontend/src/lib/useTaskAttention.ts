import { createContext, useContext } from "react";
import type { TaskAttentionSnapshot, AttentionStatus } from "@/lib/taskAttention";

export interface TaskAttentionState {
    data: TaskAttentionSnapshot | undefined;
    error: Error | null;
    status: AttentionStatus;
}
export const TaskAttentionContext = createContext<TaskAttentionState>({ data: undefined, error: null, status: "disconnected" });
export const useTaskAttention = () => useContext(TaskAttentionContext);
