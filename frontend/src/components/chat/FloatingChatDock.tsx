import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, Expand, MessageSquare, X } from "lucide-react";
import type { Project } from "@/lib/types";
import { useProjectChat } from "@/lib/useProjectChat";
import { cn } from "@/lib/cn";
import { useAgentChatStore } from "@/stores/agentChat";
import { useChatDockStore, type ChatPanel } from "@/stores/chatDock";
import { IconButton } from "@/components/ui/Button";
import { ProjectAgentWorkspace } from "@/components/agent/ProjectAgentWorkspace";
import { ProjectChatWorkspace } from "./ProjectChatWorkspace";

interface Props { project: Project; projects: Project[]; userId: number; projectPinned: boolean; fullPage: ChatPanel | null; panel: ChatPanel | null }

export function FloatingChatDock({ project, projects, userId, projectPinned, fullPage, panel }: Props) {
    const navigate = useNavigate();
    const open = useChatDockStore((state) => state.open);
    const selectProject = useChatDockStore((state) => state.selectProject);
    const conversationId = useAgentChatStore((state) => state.conversations[`${userId}:${project.id}`]);
    const { info, error } = useProjectChat();
    const unread = error ? 0 : info?.unread_count ?? 0;
    const dialog = useRef<HTMLDivElement>(null);
    const agentButton = useRef<HTMLButtonElement>(null);
    const teamButton = useRef<HTMLButtonElement>(null);
    useEffect(() => { if (panel) dialog.current?.focus(); }, [panel]);
    const close = () => { open(null); (panel === "agent" ? agentButton : teamButton).current?.focus(); };
    const expand = () => {
        open(null);
        navigate(`/projects/${project.key}/${panel === "agent" ? `agent${conversationId ? `?conversation=${conversationId}` : ""}` : "chat"}`);
    };

    return <div className="pointer-events-none fixed right-3 bottom-3 z-40 flex max-w-[calc(100vw-1.5rem)] flex-col items-end gap-3 sm:right-5 sm:bottom-5">
        {panel && <div ref={dialog} id="floating-project-chat" role="dialog" aria-modal="false" aria-label={panel === "agent" ? "Окно агента проекта" : "Окно чата команды"} tabIndex={-1}
            onKeyDown={(event) => { if (event.key === "Escape" && !event.defaultPrevented) { event.preventDefault(); event.stopPropagation(); close(); } }}
            className="pointer-events-auto flex h-[min(42rem,calc(100dvh-6.5rem))] w-[28rem] max-w-full flex-col overflow-hidden rounded-[var(--radius-panel)] border border-line bg-surface shadow-panel outline-none">
            <header className="material-glass flex shrink-0 items-center gap-2 border-b border-line-subtle px-3 py-2.5">
                <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", panel === "agent" ? "bg-ai-soft text-ai-blue" : "bg-accent-soft text-accent")}>
                    {panel === "agent" ? <Bot size={18} /> : <MessageSquare size={17} />}
                </span>
                <div className="min-w-0 flex-1">
                    <h2 className="text-[13px] font-semibold text-primary">{panel === "agent" ? "Агент проекта" : "Команда проекта"}</h2>
                    {projectPinned ? <p className="truncate text-[11px] text-muted" title={`${project.key} · ${project.name}`}>{project.key} · {project.name}</p>
                        : <select aria-label="Проект для чата" value={project.id} onChange={(event) => selectProject(userId, Number(event.target.value))} className="mt-0.5 w-full truncate rounded border border-line-subtle bg-surface py-1 text-[11px] text-secondary">
                            {projects.map((item) => <option key={item.id} value={item.id}>{item.key} · {item.name}</option>)}
                        </select>}
                </div>
                <IconButton label="Открыть чат во вкладке" onClick={expand}><Expand size={15} /></IconButton>
                <IconButton label="Свернуть чат" onClick={close}><X size={16} /></IconButton>
            </header>
            <div className="min-h-0 flex-1">
                {panel === "agent" ? <ProjectAgentWorkspace key={project.id} project={project} compact /> : <ProjectChatWorkspace key={project.id} compact />}
            </div>
        </div>}
        <div className={cn("pointer-events-auto flex max-w-full flex-col items-end gap-2", !projectPinned && !panel && "material-glass w-72 rounded-2xl border border-line p-2 shadow-panel")} aria-label="Быстрый доступ к чатам">
            {!projectPinned && !panel && <label className="flex w-full min-w-0 flex-col gap-1 px-1 pt-1">
                <span className="text-[11px] font-medium text-secondary">Чаты проекта</span>
                <select aria-label="Проект для чата" value={project.id} title={`${project.key} · ${project.name}`} onChange={(event) => selectProject(userId, Number(event.target.value))}
                    className="w-full min-w-0 truncate rounded-lg border border-accent/25 bg-surface px-2 py-2 text-[12px] font-medium text-primary outline-none hover:border-accent/50 focus-visible:border-accent focus-visible:ring-1 focus-visible:ring-accent">
                    {projects.map((item) => <option key={item.id} value={item.id}>{item.key} · {item.name}</option>)}
                </select>
            </label>}
            <div className="flex items-center gap-2">
            {fullPage !== "agent" && <button ref={agentButton} type="button" aria-label="Открыть чат агента" aria-expanded={panel === "agent"} aria-controls={panel === "agent" ? "floating-project-chat" : undefined} onClick={() => panel === "agent" ? close() : open("agent")}
                className={cn("material-glass flex h-11 items-center gap-2 rounded-full border px-4 text-xs font-medium shadow-panel transition-colors hover:border-ai-blue/60 focus-visible:outline-2 focus-visible:outline-ai-blue", panel === "agent" ? "border-ai-blue/60 text-ai-blue" : "border-line text-secondary")}>
                <Bot size={18} className="text-ai-blue" /><span>Агент</span>
            </button>}
            {fullPage !== "team" && <button ref={teamButton} type="button" aria-label="Открыть чат команды" aria-expanded={panel === "team"} aria-controls={panel === "team" ? "floating-project-chat" : undefined} onClick={() => panel === "team" ? close() : open("team")}
                className={cn("material-glass flex h-11 items-center gap-2 rounded-full border px-4 text-xs font-medium shadow-panel transition-colors hover:border-accent/60 focus-visible:outline-2 focus-visible:outline-accent", panel === "team" ? "border-accent/60 text-accent" : "border-line text-secondary")}>
                <MessageSquare size={17} className="text-accent" /><span>Команда</span>
                {unread > 0 && <span className="rounded-full bg-accent px-1.5 py-0.5 text-[10px] text-on-accent" title={`Непрочитанных сообщений: ${unread}`}>{unread > 99 ? "99+" : unread}</span>}
            </button>}
            </div>
        </div>
    </div>;
}
