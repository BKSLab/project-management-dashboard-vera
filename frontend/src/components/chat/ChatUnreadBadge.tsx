import { useProjectChat } from "@/lib/useProjectChat";

export function ChatUnreadBadge() {
    const { info, error } = useProjectChat();
    const count = error ? 0 : info?.unread_count ?? 0;
    return count > 0 ? <span aria-label={`Непрочитанных сообщений: ${count}`} className="ml-1.5 rounded bg-accent/15 px-1.5 py-0.5 font-mono text-[10px] text-accent">{count > 99 ? "99+" : count}</span> : null;
}
