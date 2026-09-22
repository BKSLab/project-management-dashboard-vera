import { createContext, useContext } from "react";
import type { ChatAck, ChatAttachment, ChatConnectionState, ChatEntity, ChatMessage, ChatMessageCreate, ChatReply, ProjectChat } from "@/lib/projectChat";

export interface ProjectChatContextValue {
    projectId: number; userId: number; info: ProjectChat | undefined; loading: boolean; error: Error | null;
    state: ChatConnectionState; online: number[]; typing: number[]; canWrite: boolean;
    command: (type: string, data?: object, messageId?: number) => Promise<ChatAck>;
    send: (body: ChatMessageCreate, presentation?: { attachments: ChatAttachment[]; entities: ChatEntity[]; reply: ChatReply | null }) => Promise<ChatMessage>;
    markRead: (message: ChatMessage) => Promise<void>;
    signalTyping: (active: boolean) => void;
}
export const ProjectChatContext = createContext<ProjectChatContextValue | null>(null);

export function useProjectChat() {
    const value = useContext(ProjectChatContext);
    if (!value) throw new Error("Чат должен находиться внутри проекта.");
    return value;
}
