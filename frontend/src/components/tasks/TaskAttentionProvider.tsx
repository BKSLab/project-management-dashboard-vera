import { useEffect, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";
import { useCurrentUser } from "@/lib/useAuth";
import { attentionEndpoint, attentionKey, connectTaskAttention, type AttentionStatus, type TaskAttentionSnapshot } from "@/lib/taskAttention";
import { TaskAttentionContext } from "@/lib/useTaskAttention";

export function TaskAttentionProvider({ children }: { children: ReactNode }) {
    const { data: user } = useCurrentUser();
    const userId = user?.id;
    const client = useQueryClient();
    const [status, setStatus] = useState<AttentionStatus>("disconnected");
    const key = attentionKey(userId ?? 0);
    const query = useQuery({
        queryKey: key,
        queryFn: () => api.get<TaskAttentionSnapshot>(attentionEndpoint),
        enabled: userId !== undefined,
        refetchInterval: status === "connected" ? false : 30_000,
        retry: false,
    });
    useEffect(() => {
        if (userId === undefined) return;
        const queryKey = attentionKey(userId);
        let disposed = false;
        return (() => {
            const close = connectTaskAttention({
                onStatus: setStatus,
                onSnapshot: async data => {
                    const old = client.getQueryData<TaskAttentionSnapshot>(queryKey);
                    await client.cancelQueries({ queryKey });
                    if (disposed) return;
                    client.setQueryData(queryKey, data);
                    const previous = new Map(old?.items.map(item => [item.task_id, item.revision]));
                    const changed = data.items.filter(item => previous.get(item.task_id) !== item.revision);
                    if (changed.length || (old && old.items.length !== data.items.length)) {
                        void client.invalidateQueries({ queryKey: queryKeys.myTasks });
                        for (const item of changed) {
                            void client.invalidateQueries({ queryKey: queryKeys.task(item.task_id) });
                            void client.invalidateQueries({ queryKey: queryKeys.taskComments(item.task_id) });
                            void client.invalidateQueries({ queryKey: queryKeys.taskActivity(item.task_id) });
                        }
                    }
                },
            });
            return () => { disposed = true; close(); };
        })();
    }, [userId, client]);
    return <TaskAttentionContext.Provider value={{ data: query.data, error: query.error as Error | null, status }}>{children}</TaskAttentionContext.Provider>;
}
