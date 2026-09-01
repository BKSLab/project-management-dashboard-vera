import { apiUrl, authEndpoints } from "@/lib/api";
import { cn } from "@/lib/cn";
import { initials, type User } from "@/lib/types";

const SIZES = {
    sm: "size-7 text-[10px]",
    md: "size-9 text-[12px]",
    lg: "size-20 text-[22px]",
} as const;

interface UserAvatarProps {
    user: User;
    size?: keyof typeof SIZES;
    /** Меняется после загрузки новой фотографии, чтобы обойти кэш браузера. */
    version?: number;
    className?: string;
}

/** Фотография профиля или инициалы, если она не загружена. */
export function UserAvatar({ user, size = "md", version = 0, className }: UserAvatarProps) {
    const shared = cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full",
        SIZES[size],
        className,
    );

    if (!user.has_avatar) {
        return (
            <span
                aria-hidden="true"
                className={cn(shared, "bg-surface-2 font-semibold text-secondary")}
            >
                {initials(user)}
            </span>
        );
    }

    return (
        <img
            src={`${apiUrl(authEndpoints.avatar())}?v=${version}`}
            alt=""
            className={cn(shared, "object-cover")}
        />
    );
}
