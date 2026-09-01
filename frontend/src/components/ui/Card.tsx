import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
    /** Добавляет hover-подъём. Только для кликабельных карточек. */
    interactive?: boolean;
}

export function Card({ interactive = false, className, children, ...props }: CardProps) {
    return (
        <div
            className={cn(
                "rounded-lg border border-line bg-surface shadow-card",
                interactive &&
                    "transition-[background-color,border-color,box-shadow,transform] " +
                        "duration-[var(--duration-normal)] ease-[var(--ease-standard)] " +
                        "hover:-translate-y-px hover:border-line-strong hover:bg-surface-2 hover:shadow-elevated",
                className,
            )}
            {...props}
        >
            {children}
        </div>
    );
}

interface SectionProps {
    title: string;
    action?: ReactNode;
    children: ReactNode;
    className?: string;
}

/** Секция рабочего экрана: заголовок, необязательное действие и содержимое. */
export function Section({ title, action, children, className }: SectionProps) {
    return (
        <section className={cn("flex min-w-0 flex-col gap-3", className)}>
            <div className="flex items-center justify-between gap-3">
                <h2 className="text-[13px] font-semibold text-secondary">{title}</h2>
                {action}
            </div>
            {children}
        </section>
    );
}
