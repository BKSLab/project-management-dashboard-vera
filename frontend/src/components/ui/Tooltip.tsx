import type { ReactElement, ReactNode } from "react";
import {
    Tooltip as AriaTooltip,
    TooltipTrigger,
    type TooltipProps as AriaTooltipProps,
} from "react-aria-components";
import { cn } from "@/lib/cn";

interface TooltipProps {
    children: ReactElement;
    content: ReactNode;
    placement?: AriaTooltipProps["placement"];
    className?: string;
}

/** Portal-based tooltip: не обрезается overflow-контейнерами shell/drawer. */
export function Tooltip({ children, content, placement = "right", className }: TooltipProps) {
    return (
        <TooltipTrigger delay={450} closeDelay={0}>
            {children}
            <AriaTooltip
                placement={placement}
                offset={7}
                className={cn(
                    "material-glass z-[80] max-w-64 rounded-[var(--radius-control)]",
                    "px-2 py-1 text-[11px] text-secondary shadow-panel",
                    className,
                )}
            >
                {content}
            </AriaTooltip>
        </TooltipTrigger>
    );
}
