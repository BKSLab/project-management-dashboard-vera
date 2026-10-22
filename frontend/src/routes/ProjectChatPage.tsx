import { lazy, Suspense } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Database, History, MessageSquare, MoreHorizontal } from "lucide-react";
import { ProjectChatWorkspace } from "@/components/chat/ProjectChatWorkspace";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { Button } from "@/components/ui/Button";
import { Popover } from "@/components/ui/Popover";
import { Skeleton } from "@/components/ui/States";

const ProjectAgentWorkspace = lazy(() => import("@/components/agent/ProjectAgentWorkspace").then((module) => ({ default: module.ProjectAgentWorkspace })));

export function ProjectChatPage() {
    const project = useProjectOutlet();
    const location = useLocation();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const view = params.get("view");
    const personal = view === "personal";
    const knowledge = view === "knowledge";
    const select = (nextView: "personal" | "knowledge" | null) => {
        const next = new URLSearchParams(params);
        if (nextView) next.set("view", nextView);
        else next.delete("view");
        navigate({ pathname: location.pathname, search: next.toString(), hash: location.hash });
    };
    return <section className="flex h-full min-h-0 flex-col" aria-label="Чат проекта">
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-b border-line-subtle px-4 py-2">
            {personal && <p className="mr-auto text-[11px] text-muted">Личные диалоги по проекту · видите только вы</p>}
            {knowledge && <p className="mr-auto text-[11px] font-medium text-secondary">Знания проекта</p>}
            {(personal || knowledge) && <Button size="sm" variant="ghost" icon={<MessageSquare size={14} />} onClick={() => select(null)}>Общий чат</Button>}
            <Popover label="Личные диалоги и знания" width={264} trigger={<span className="flex items-center gap-2"><MoreHorizontal size={16} aria-hidden="true" /><span className="text-xs">Личные диалоги и знания</span></span>}>
                {({ close }) => <div className="p-1">
                    <button type="button" onClick={() => { select("personal"); close(); }} className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-xs text-secondary hover:bg-hover"><History size={15} aria-hidden="true" />Личные диалоги</button>
                    <button type="button" onClick={() => { select("knowledge"); close(); }} className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-xs text-secondary hover:bg-hover"><Database size={15} aria-hidden="true" />Знания проекта</button>
                </div>}
            </Popover>
        </div>
        <div className="min-h-0 flex-1">
            {personal || knowledge ? <Suspense fallback={<div className="p-5"><Skeleton className="h-48 w-full" /></div>}>
                <ProjectAgentWorkspace key={project.id} project={project} knowledgeOnly={knowledge} />
            </Suspense> : <ProjectChatWorkspace />}
        </div>
    </section>;
}
