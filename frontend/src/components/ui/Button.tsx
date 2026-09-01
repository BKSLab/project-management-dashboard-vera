import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { cn } from "@/lib/cn";

const base =
    "inline-flex items-center justify-center gap-2 rounded-md font-medium " +
    "transition-[background-color,border-color,color,box-shadow] duration-[var(--duration-normal)] " +
    "ease-[var(--ease-standard)] disabled:cursor-not-allowed disabled:opacity-55 " +
    "disabled:hover:bg-inherit";

const variants = {
    primary: "bg-accent text-[#0d1117] font-semibold hover:bg-accent-hover active:brightness-95",
    secondary:
        "border border-line bg-surface-2 text-primary hover:border-line-strong hover:bg-hover active:bg-active",
    ghost: "text-secondary hover:bg-hover hover:text-primary active:bg-active",
    destructive:
        "border border-danger/40 bg-danger/10 text-danger hover:border-danger/60 hover:bg-danger/20",
} as const;

const sizes = {
    sm: "h-7 px-2.5 text-[13px]",
    md: "h-8 px-3 text-[13px]",
    lg: "h-9 px-4 text-sm",
} as const;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: keyof typeof variants;
    size?: keyof typeof sizes;
    icon?: ReactNode;
}

export function Button({
    variant = "secondary",
    size = "md",
    icon,
    className,
    type = "button",
    children,
    ...props
}: ButtonProps) {
    return (
        <button
            type={type}
            className={cn(base, variants[variant], sizes[size], className)}
            {...props}
        >
            {icon}
            {children}
        </button>
    );
}

interface LinkButtonProps extends LinkProps {
    variant?: keyof typeof variants;
    size?: keyof typeof sizes;
    icon?: ReactNode;
}

/** Ссылка с видом кнопки: настоящий `a`, а не кнопка с вложенной ссылкой. */
export function LinkButton({
    variant = "secondary",
    size = "md",
    icon,
    className,
    children,
    ...props
}: LinkButtonProps) {
    return (
        <Link className={cn(base, variants[variant], sizes[size], className)} {...props}>
            {icon}
            {children}
        </Link>
    );
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    /** Обязателен: кнопка без текста непонятна без доступного имени (раздел 15). */
    label: string;
    variant?: keyof typeof variants;
    size?: "sm" | "md";
}

export function IconButton({
    label,
    variant = "ghost",
    size = "md",
    className,
    type = "button",
    children,
    ...props
}: IconButtonProps) {
    return (
        <button
            type={type}
            aria-label={label}
            title={label}
            className={cn(
                base,
                variants[variant],
                size === "sm" ? "h-6 w-6" : "h-8 w-8",
                "shrink-0 p-0",
                className,
            )}
            {...props}
        >
            {children}
        </button>
    );
}
