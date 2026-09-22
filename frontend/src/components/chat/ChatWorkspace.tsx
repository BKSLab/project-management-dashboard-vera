import { useEffect, type ReactNode } from "react";
import { useMatch } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import { useCurrentUser } from "@/lib/useAuth";
import type { Project } from "@/lib/types";
import { useChatDockStore } from "@/stores/chatDock";
import { ProjectChatProvider } from "./ProjectChatProvider";
import { FloatingChatDock } from "./FloatingChatDock";

/** Один транспорт для вкладки и окна, в том числе вне страниц проекта. */
export function ChatWorkspace({ children }: { children: ReactNode }) {
    const userId = useCurrentUser().data?.id ?? 0;
    const match = useMatch("/projects/:projectKey/*");
    const projectKey = match?.params.projectKey === "new" ? undefined : match?.params.projectKey;
    const projects = useQuery({ queryKey: queryKeys.projects, queryFn: () => api.get<Project[]>(endpoints.projects()), enabled: userId > 0 }).data;
    const selectedId = useChatDockStore((state) => state.projects[userId]);
    const selectProject = useChatDockStore((state) => state.selectProject);
    const panel = useChatDockStore((state) => state.panel);
    const open = useChatDockStore((state) => state.open);
    const project = projectKey
        ? projects?.find((item) => item.key.toUpperCase() === projectKey.toUpperCase())
        : projects?.find((item) => item.id === selectedId) ?? projects?.[0];
    const section = match?.params["*"]?.replace(/\/$/, "");
    const fullPage = section === "chat" ? "team" : section === "agent" || section === "knowledge" ? "agent" : null;
    const visiblePanel = panel === fullPage ? null : panel;

    useEffect(() => {
        if (project && project.id !== selectedId) selectProject(userId, project.id);
    }, [project, selectedId, userId, selectProject]);
    useEffect(() => { if (fullPage === panel) open(null); }, [fullPage, panel, open]);
    useEffect(() => () => { useChatDockStore.getState().open(null); }, [userId]);

    return <ProjectChatProvider projectId={project?.id ?? 0} projectKey={project?.key ?? ""} chatVisible={fullPage === "team" || visiblePanel === "team"}>
        {children}
        {project && userId > 0 && <FloatingChatDock project={project} projects={projects ?? []} userId={userId} projectPinned={Boolean(projectKey)} fullPage={fullPage} panel={visiblePanel} />}
    </ProjectChatProvider>;
}
