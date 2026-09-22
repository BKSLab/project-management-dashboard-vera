import { useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { chatKeys, chatPath, mergeChatMessages, type ChatHistory, type ChatMessagePage } from "@/lib/projectChat";

/** Один канонический кэш страницы/окружения; WS и HTTP обновляют его совместно. */
export function useChatMessages(projectId: number, userId: number, enabled: boolean, around?: number) {
    const client = useQueryClient();
    const key = useMemo(() => around ? [...chatKeys.messages(projectId, userId), "around", around] : chatKeys.messages(projectId, userId), [around, projectId, userId]);
    const query = useQuery({
        queryKey: key,
        queryFn: async (): Promise<ChatHistory> => {
            const page = await api.get<ChatMessagePage>(`${chatPath(projectId)}/messages${around ? `?around=${around}` : ""}`);
            const current = client.getQueryData<ChatHistory>(key);
            const updates = current?.messages.filter((message) => message.delivery || (message.eventSeq ?? 0) > page.event_cursor) ?? [];
            return { ...page, messages: mergeChatMessages(page.messages.map((message) => ({ ...message, eventSeq: page.event_cursor })), updates), initialized: true };
        },
        enabled, staleTime: Infinity, refetchOnWindowFocus: false, refetchOnMount: "always", retry: false,
    });
    const loadOlder = useCallback(async () => {
        const current = client.getQueryData<ChatHistory>(key);
        const first = current?.messages.find((row) => !row.delivery);
        if (!current || !first || !current.has_more) return;
        const page = await api.get<ChatMessagePage>(`${chatPath(projectId)}/messages?before=${first.seq}`);
        client.setQueryData<ChatHistory>(key, (old) => old && ({ ...old, messages: mergeChatMessages(page.messages.map((message) => ({ ...message, eventSeq: page.event_cursor })), old.messages), has_more: page.has_more }));
    }, [client, key, projectId]);
    return { ...query, loadOlder };
}
