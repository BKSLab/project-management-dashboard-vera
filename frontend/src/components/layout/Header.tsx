import { NavLink } from "react-router-dom";

const navItems = [
    { to: "/docs", label: "Документы" },
    { to: "/wbs", label: "ИСР" },
    { to: "/kanban", label: "Канбан" },
];

export function Header() {
    return (
        <header
            className="sticky top-0 z-40 border-b border-white/[0.06] backdrop-blur-md backdrop-saturate-150"
            style={{ backgroundColor: "rgba(36,43,61,0.65)" }}
        >
            <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4">
                <NavLink to="/" className="min-w-0 shrink font-black tracking-[0.04em] text-foreground">
                    <span className="whitespace-nowrap">Агент Вера</span>
                    <span className="hidden sm:inline"> · Дашборд</span>
                </NavLink>
                <nav className="flex shrink-0 items-center gap-3 sm:gap-6" aria-label="Основная навигация">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className="text-xs text-muted transition-colors hover:text-foreground sm:text-sm"
                        >
                            {item.label}
                        </NavLink>
                    ))}
                </nav>
            </div>
        </header>
    );
}
