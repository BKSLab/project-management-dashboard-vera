/** Общий контракт HTTP/WS. Серверный seq задаёт порядок внутри проекта. */
export type ChatEntityType = "TASK" | "DOCUMENT" | "RISK" | "MILESTONE" | "WBS_NODE";
export interface ChatUser { id: number; username: string; display_name: string }
export interface ChatEntityRef { entity_type: ChatEntityType; entity_id: number }
export interface ChatEntity extends ChatEntityRef {
    title: string; available: boolean; status: string | null; subtitle: string | null; href: string | null;
}
export interface ChatAttachment {
    id: string; original_name: string; content_type: string; size_bytes: number;
    message_id: number | null; created_at: string;
}
export interface ChatReply { id: number; seq: number; author: ChatUser | null; content: string; deleted: boolean }
export interface ChatMessageBody {
    content: string; mentions: number[]; entities: ChatEntityRef[]; attachment_ids: string[];
}
export interface ChatMessageCreate extends ChatMessageBody { client_message_id: string; reply_to_message_id: number | null }
export interface ChatMessage {
    id: number; chat_id: number; project_id: number; seq: number; author_type: "USER";
    author: ChatUser | null; client_message_id: string; content: string; revision: number;
    created_at: string; edited_at: string | null; deleted_at: string | null;
    reply: ChatReply | null; mentions: ChatUser[]; entities: ChatEntity[]; attachments: ChatAttachment[];
    reactions: { reaction: string; user_ids: number[] }[];
    /** Только клиентские поля оптимистичной строки, не отдельное хранилище истории. */
    delivery?: "sending" | "failed";
    error?: string;
    pendingBody?: ChatMessageCreate;
    eventSeq?: number;
}
export interface ProjectChat {
    id: number; project_id: number; event_cursor: number; last_read_seq: number; unread_count: number; members: ChatUser[];
}
export interface ChatMessagePage { messages: ChatMessage[]; has_more: boolean; event_cursor: number }
export interface ChatHistory extends ChatMessagePage { initialized?: boolean }
export interface ChatEvent {
    type: string; project_id: number; seq?: number;
    data: { message?: ChatMessage; message_id?: number; user_id?: number; user_ids?: number[]; last_read_seq?: number; entity_type?: ChatEntityType; entity_id?: number };
}
export interface ChatEventPage { events: ChatEvent[]; cursor: number; has_more: boolean }
export interface ChatAck { message?: ChatMessage; client_message_id?: string; last_read_seq?: number; unread_count?: number }
export type ChatConnectionState = "connecting" | "syncing" | "connected" | "reconnecting" | "unavailable" | "forbidden";
export const CHAT_REACTIONS = ["👍", "❤️", "👀", "✅", "🎉"] as const;
export const chatPath = (projectId: number) => `/api/v1/projects/${projectId}/chat`;
export const chatKeys = {
    root: (projectId: number, userId: number) => ["project-chat", projectId, userId] as const,
    info: (projectId: number, userId: number) => [...chatKeys.root(projectId, userId), "info"] as const,
    messages: (projectId: number, userId: number) => [...chatKeys.root(projectId, userId), "messages"] as const,
    entities: (projectId: number, userId: number) => [...chatKeys.root(projectId, userId), "entities"] as const,
    search: (projectId: number, userId: number) => [...chatKeys.root(projectId, userId), "search"] as const,
};

/** Схлопывает ack/broadcast/retry по автору и UUID, сохраняя серверный порядок. */
export function mergeChatMessages(previous: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
    const rows = new Map(previous.map((row) => [`${row.author?.id ?? 0}:${row.client_message_id}`, row]));
    const keysById = new Map(previous.filter((row) => row.id > 0).map((row) => [row.id, `${row.author?.id ?? 0}:${row.client_message_id}`]));
    for (const row of incoming) {
        const key = `${row.author?.id ?? 0}:${row.client_message_id}`;
        const priorKey = row.id > 0 ? keysById.get(row.id) : undefined;
        const current = rows.get(key) ?? (priorKey ? rows.get(priorKey) : undefined);
        if (current && !current.delivery && row.delivery) continue;
        if (current && current.revision > row.revision) continue;
        if (current?.eventSeq && row.eventSeq && current.eventSeq > row.eventSeq) continue;
        // Запоздалый ack не откатывает уже применённое событие реакции той же версии.
        if (current?.eventSeq && row.eventSeq === undefined && !row.delivery && current.revision >= row.revision) continue;
        if (priorKey && priorKey !== key) rows.delete(priorKey);
        rows.set(key, { ...row, eventSeq: row.eventSeq ?? current?.eventSeq });
        if (row.id > 0) keysById.set(row.id, key);
    }
    return [...rows.values()].sort((a, b) => (a.delivery ? Number.MAX_SAFE_INTEGER : a.seq) - (b.delivery ? Number.MAX_SAFE_INTEGER : b.seq) || a.created_at.localeCompare(b.created_at));
}

/** Обновляет и саму реплику, и previews ответов на неё. */
export function applyChatMessage(history: ChatHistory | undefined, message: ChatMessage): ChatHistory {
    const messages = mergeChatMessages(history?.messages ?? [], [message]).map((row) => row.reply?.id === message.id ? {
        ...row, reply: { id: message.id, seq: message.seq, author: message.author, content: message.deleted_at ? "Сообщение удалено" : message.content.slice(0, 240), deleted: Boolean(message.deleted_at) },
    } : row);
    return { messages, has_more: history?.has_more ?? false, event_cursor: Math.max(history?.event_cursor ?? 0, message.eventSeq ?? 0), initialized: history?.initialized ?? false };
}
