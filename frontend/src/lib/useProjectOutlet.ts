import { useOutletContext } from "react-router-dom";
import type { Project } from "@/lib/types";

interface ProjectOutletContext {
    project: Project;
}

/** Проект, уже загруженный оболочкой рабочего пространства. */
export function useProjectOutlet(): Project {
    return useOutletContext<ProjectOutletContext>().project;
}
