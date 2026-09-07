import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, endpoints, queryKeys } from "@/lib/api";
import { fullName, type Project, type ProjectMember } from "@/lib/types";

export function ProjectPeopleSummary({ project }: { project: Project }) {
    const query = useQuery({
        queryKey: queryKeys.projectMembers(project.id),
        queryFn: () => api.get<ProjectMember[]>(endpoints.projectMembers(project.id)),
    });
    if (query.isPending) return <p role="status" className="text-[12px] text-muted">Загрузка команды…</p>;
    if (query.error) return <p role="alert" className="text-[12px] text-danger">Не удалось загрузить сведения о команде.</p>;
    const members = query.data ?? [];
    const manager = members.find((member) => member.user.id === project.owner_id) ?? members.find((member) => member.role === "OWNER");
    return (
        <dl className="flex flex-col gap-2 text-[13px]">
            <div className="flex flex-wrap gap-x-2"><dt className="text-muted">Руководитель:</dt><dd className="text-secondary">{manager ? fullName(manager.user) : "Не указан"}</dd></div>
            <div className="flex flex-wrap gap-x-2"><dt className="text-muted">Команда:</dt><dd>
                <Link to={`/projects/${project.key}/team`} className="text-accent hover:underline">
                    {members.length ? members.map((member) => fullName(member.user)).join(", ") : "Открыть команду"}
                </Link>
            </dd></div>
        </dl>
    );
}
