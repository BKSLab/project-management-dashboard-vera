import { cn } from "@/lib/cn";

interface BadgeProps {
    children: React.ReactNode;
    className?: string;
}

export function Badge({ children, className }: BadgeProps) {
    return (
        <span
            className={cn(
                "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-surface-elevated text-muted",
                className
            )}
        >
            {children}
        </span>
    );
}
