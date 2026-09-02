import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
    FolderKanban,
    LayoutDashboard,
    PanelLeftClose,
    PanelLeftOpen,
    Plug,
    Plus,
} from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/cn";
import { useUiStore } from "@/stores/ui";
import { IconButton } from "@/components/ui/Button";
import { StatusDot } from "@/components/ui/Badge";
import { UserMenu } from "@/components/users/UserMenu";
import { useCurrentUser } from "@/lib/useAuth";

const GLOBAL_ITEMS = [
    { to: "/", label: "Дашборд", icon: LayoutDashboard, end: true },
    { to: "/projects", label: "Проекты", icon: FolderKanban, end: false },
    { to: "/mcp", label: "MCP", icon: Plug, end: false },
];

function navLinkClass(isActive: boolean, collapsed: boolean): string {
    return cn(
        "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px]",
        "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
        collapsed && "justify-center px-0",
        isActive
            ? "bg-accent-soft text-accent"
            : "text-secondary hover:bg-hover hover:text-primary",
    );
}

export function Sidebar() {
    const collapsed = useUiStore((state) => state.sidebarCollapsed);
    const toggleSidebar = useUiStore((state) => state.toggleSidebar);

    const { data: user } = useCurrentUser();

    const projectsQuery = useQuery({
        queryKey: queryKeys.projects,
        queryFn: () => api.get<Project[]>(endpoints.projects()),
    });

    return (
        <aside
            className={cn(
                "hidden shrink-0 flex-col border-r border-line bg-sidebar md:flex",
                "transition-[width] duration-[var(--duration-normal)] ease-[var(--ease-standard)]",
                collapsed ? "w-14" : "w-56",
            )}
        >
            <div
                className={cn(
                    "flex h-12 shrink-0 items-center border-b border-line px-2",
                    collapsed ? "justify-center" : "justify-between",
                )}
            >
                {!collapsed && (
                    <span className="truncate px-1 text-[13px] font-semibold text-primary">
                        Task Tracker
                    </span>
                )}
                <IconButton
                    label={collapsed ? "Развернуть панель" : "Свернуть панель"}
                    size="sm"
                    onClick={toggleSidebar}
                >
                    {collapsed ? <PanelLeftOpen size={14} /> : <PanelLeftClose size={14} />}
                </IconButton>
            </div>

            <nav aria-label="Основная навигация" className="flex flex-col gap-0.5 p-2">
                {GLOBAL_ITEMS.map(({ to, label, icon: Icon, end }) => (
                    <NavLink
                        key={to}
                        to={to}
                        end={end}
                        title={collapsed ? label : undefined}
                        className={({ isActive }) => navLinkClass(isActive, collapsed)}
                    >
                        <Icon size={16} aria-hidden="true" className="shrink-0" />
                        {!collapsed && <span className="truncate">{label}</span>}
                    </NavLink>
                ))}
            </nav>

            <div className="scrollbar-thin flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto border-t border-line p-2">
                {!collapsed && (
                    <p className="px-2 pt-1 pb-2 text-[11px] font-medium tracking-[0.06em] text-disabled uppercase">
                        Проекты
                    </p>
                )}
                {projectsQuery.data?.map((project) => (
                    <NavLink
                        key={project.id}
                        to={`/projects/${project.key}`}
                        title={collapsed ? project.name : undefined}
                        className={({ isActive }) => navLinkClass(isActive, collapsed)}
                    >
                        {project.icon ? (
                            <span aria-hidden="true" className="shrink-0 text-sm leading-none">
                                {project.icon}
                            </span>
                        ) : (
                            <StatusDot color={project.color} />
                        )}
                        {!collapsed && <span className="truncate">{project.name}</span>}
                    </NavLink>
                ))}
                <NavLink
                    to="/projects/new"
                    title={collapsed ? "Новый проект" : undefined}
                    className={({ isActive }) => navLinkClass(isActive, collapsed)}
                >
                    <Plus size={16} aria-hidden="true" className="shrink-0" />
                    {!collapsed && <span className="truncate">Новый проект</span>}
                </NavLink>
            </div>

            {user && <UserMenu user={user} collapsed={collapsed} />}
        </aside>
    );
}
