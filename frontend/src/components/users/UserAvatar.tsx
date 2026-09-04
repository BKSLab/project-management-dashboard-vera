import { useState } from "react";
import { apiUrl, authEndpoints } from "@/lib/api";
import { cn } from "@/lib/cn";
import { initials, type UserSummary } from "@/lib/types";

const SIZES = {
    xs: "size-[22px] text-[8px]",
    sm: "size-7 text-[10px]",
    md: "size-9 text-[12px]",
    lg: "size-20 text-[22px]",
} as const;

interface UserAvatarProps {
    user?: UserSummary;
    size?: keyof typeof SIZES;
    /** Меняется после загрузки новой фотографии, чтобы обойти кэш браузера. */
    version?: number;
    /** Project-scoped URL нужен для фотографий других участников. */
    avatarUrl?: string;
    fallbackInitials?: string;
    hasAvatar?: boolean;
    className?: string;
}

/** Фотография профиля или инициалы, если она не загружена. */
export function UserAvatar({
    user,
    size = "md",
    version = 0,
    avatarUrl,
    fallbackInitials,
    hasAvatar,
    className,
}: UserAvatarProps) {
    const source = avatarUrl ?? `${apiUrl(authEndpoints.avatar())}?v=${version}`;
    const [failedSource, setFailedSource] = useState<string | null>(null);
    const canLoadImage = (hasAvatar ?? user?.has_avatar ?? false) && failedSource !== source;
    const shared = cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full",
        SIZES[size],
        className,
    );

    if (!canLoadImage) {
        return (
            <span
                aria-hidden="true"
                className={cn(shared, "bg-surface-2 font-semibold text-secondary")}
            >
                {fallbackInitials ?? (user ? initials(user) : "?")}
            </span>
        );
    }

    return (
        <img
            src={source}
            alt=""
            loading="lazy"
            onError={() => setFailedSource(source)}
            className={cn(shared, "object-cover")}
        />
    );
}
