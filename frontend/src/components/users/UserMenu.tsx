import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { cn } from "@/lib/cn";
import { fullName, type User } from "@/lib/types";
import { useLogout } from "@/lib/useAuth";
import { IconButton } from "@/components/ui/Button";
import { UserAvatar } from "@/components/users/UserAvatar";

interface UserMenuProps {
    user: User;
    collapsed: boolean;
}

/** Карточка пользователя внизу сайдбара: профиль и выход. */
export function UserMenu({ user, collapsed }: UserMenuProps) {
    const navigate = useNavigate();
    const logout = useLogout();

    return (
        <div
            className={cn(
                "flex shrink-0 items-center gap-2 border-t border-line p-2",
                collapsed && "flex-col gap-1",
            )}
        >
            <button
                type="button"
                onClick={() => navigate("/profile")}
                title={collapsed ? fullName(user) : undefined}
                className={cn(
                    "flex min-w-0 flex-1 items-center gap-2 rounded-md px-1 py-1 text-left",
                    "transition-colors duration-[var(--duration-fast)] hover:bg-hover",
                    collapsed && "flex-none justify-center",
                )}
            >
                <UserAvatar user={user} size="sm" />
                {!collapsed && (
                    <span className="flex min-w-0 flex-col">
                        <span className="truncate text-[12px] font-medium text-secondary">
                            {fullName(user)}
                        </span>
                        <span className="truncate font-mono text-[10px] text-disabled">
                            {user.username}
                        </span>
                    </span>
                )}
            </button>

            <IconButton
                label="Выйти"
                size="sm"
                disabled={logout.isPending}
                onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login") })}
            >
                <LogOut size={13} aria-hidden="true" />
            </IconButton>
        </div>
    );
}
