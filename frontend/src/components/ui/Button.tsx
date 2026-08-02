import { cn } from "@/lib/cn";
import type { ButtonHTMLAttributes } from "react";

const variants = {
    primary:
        "rounded-md bg-accent px-4 py-2 font-semibold text-accent-foreground transition-colors duration-150 hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60",
    secondary:
        "rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-sm font-semibold text-foreground transition-colors duration-150 hover:border-white/20 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60",
    neutral:
        "rounded-md bg-surface-hover px-3 py-1.5 text-sm font-medium text-foreground transition-colors duration-150 hover:bg-surface-active focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60",
} as const;

type ButtonVariant = keyof typeof variants;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: ButtonVariant;
}

export function Button({
    variant = "secondary",
    className,
    type = "button",
    ...props
}: ButtonProps) {
    return (
        <button
            type={type}
            className={cn(variants[variant], className)}
            {...props}
        />
    );
}
