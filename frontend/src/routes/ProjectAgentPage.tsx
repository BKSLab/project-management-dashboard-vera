import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { ProjectAgentWorkspace } from "@/components/agent/ProjectAgentWorkspace";

export function ProjectAgentPage() {
    const project = useProjectOutlet();
    return <ProjectAgentWorkspace key={project.id} project={project} />;
}
