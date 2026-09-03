import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface ProgressBarProps {
    /** Доля выполненного от 0 до 1. */
    value: number;
    label?: string;
    color?: string;
    className?: string;
}

export function ProgressBar({ value, label, color, className }: ProgressBarProps) {
    const percent = Math.round(Math.min(Math.max(value, 0), 1) * 100);
    return (
        <div
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={label ?? "Прогресс"}
            className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-2", className)}
        >
            <div
                className="h-full rounded-full transition-[width] duration-[var(--duration-slow)] ease-[var(--ease-standard)]"
                style={{ width: `${percent}%`, backgroundColor: color ?? "var(--color-accent)" }}
            />
        </div>
    );
}

interface SegmentedProgressProps {
    segments: { id: number | string; value: number; color: string; label: string }[];
    className?: string;
}

/** Многосегментная шкала: распределение задач по стадиям одной полосой. */
export function SegmentedProgress({ segments, className }: SegmentedProgressProps) {
    const total = segments.reduce((sum, segment) => sum + segment.value, 0);
    if (total === 0) {
        return <div className={cn("h-1.5 w-full rounded-full bg-surface-2", className)} />;
    }
    return (
        <div className={cn("flex h-1.5 w-full overflow-hidden rounded-full bg-surface-2", className)}>
            {segments
                .filter((segment) => segment.value > 0)
                .map((segment) => (
                    <div
                        key={segment.id}
                        title={`${segment.label}: ${segment.value}`}
                        style={{
                            width: `${(segment.value / total) * 100}%`,
                            backgroundColor: segment.color,
                        }}
                    />
                ))}
        </div>
    );
}

interface StatTileProps {
    label: string;
    value: ReactNode;
    hint?: string;
    tone?: "default" | "warning" | "danger" | "success";
    icon?: ReactNode;
}

export function StatStrip({ children, className }: { children: ReactNode; className?: string }) {
    return (
        <div
            className={cn(
                "grid grid-cols-2 overflow-hidden rounded-[var(--radius-card)]",
                "border border-line-subtle bg-surface shadow-card lg:grid-cols-4",
                "[&>*:nth-child(even)]:border-l [&>*:nth-child(even)]:border-line-subtle",
                "lg:[&>*+*]:border-l lg:[&>*+*]:border-line-subtle",
                className,
            )}
        >
            {children}
        </div>
    );
}

const TONE_CLASSES = {
    default: "text-primary",
    warning: "text-warning",
    danger: "text-danger",
    success: "text-success",
} as const;

export function StatTile({ label, value, hint, tone = "default", icon }: StatTileProps) {
    return (
        <div className="flex min-w-0 flex-col gap-1 px-4 py-3.5">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted">
                {icon}
                <span className="truncate">{label}</span>
            </div>
            <div className={cn("font-mono text-[22px] leading-none font-semibold tracking-[-0.03em]", TONE_CLASSES[tone])}>
                {value}
            </div>
            {hint && <p className="truncate text-[11px] text-muted">{hint}</p>}
        </div>
    );
}
