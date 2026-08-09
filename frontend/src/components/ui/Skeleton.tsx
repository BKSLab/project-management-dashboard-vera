import { cn } from "@/lib/cn";

interface SkeletonProps {
    className?: string;
}

/** Базовый пульсирующий блок — из него собираются скелетоны конкретных секций. */
export function Skeleton({ className }: SkeletonProps) {
    return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-white/10", className)} />;
}
