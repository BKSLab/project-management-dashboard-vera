import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { FolderKanban, LayoutDashboard } from "lucide-react";
import { cn } from "@/lib/cn";
import { Sidebar } from "@/components/layout/Sidebar";
import { ToastViewport } from "@/components/ui/Toast";

const MOBILE_ITEMS = [
    { to: "/", label: "Дашборд", icon: LayoutDashboard, end: true },
    { to: "/projects", label: "Проекты", icon: FolderKanban, end: false },
];

/**
 * Каркас приложения: сворачиваемый сайдбар на десктопе и компактная
 * навигация на узких экранах (раздел 19 дизайн-гайда).
 */
export function AppShell({ children }: { children: ReactNode }) {
    return (
        <div className="flex h-screen min-w-0 overflow-hidden bg-app">
            <a
                href="#main-content"
                className={cn(
                    "sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[70]",
                    "focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-[13px]",
                    "focus:font-semibold focus:text-on-accent",
                )}
            >
                Перейти к содержимому
            </a>

            <Sidebar />

            <div className="flex min-w-0 flex-1 flex-col">
                <nav
                    aria-label="Разделы"
                    className="material-metal flex h-12 shrink-0 items-center gap-1 border-b border-line-subtle px-3 md:hidden"
                >
                    {MOBILE_ITEMS.map(({ to, label, icon: Icon, end }) => (
                        <NavLink
                            key={to}
                            to={to}
                            end={end}
                            className={({ isActive }) =>
                                cn(
                                    "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px]",
                                    isActive
                                        ? "bg-accent-soft text-accent"
                                        : "text-secondary hover:bg-hover hover:text-primary",
                                )
                            }
                        >
                            <Icon size={15} aria-hidden="true" />
                            {label}
                        </NavLink>
                    ))}
                </nav>

                <main id="main-content" className="material-mineral min-w-0 flex-1 overflow-hidden">
                    {children}
                </main>
            </div>

            <ToastViewport />
        </div>
    );
}

interface PageProps {
    children: ReactNode;
    className?: string;
}

/** Обычная прокручиваемая страница с внутренними отступами. */
export function Page({ children, className }: PageProps) {
    return (
        <div className="scrollbar-thin h-full overflow-y-auto">
            <div className={cn("mx-auto flex w-full max-w-6xl flex-col gap-6 px-5 py-6 sm:px-6", className)}>
                {children}
            </div>
        </div>
    );
}
