import {
    useCallback,
    useEffect,
    useId,
    useLayoutEffect,
    useRef,
    useState,
    type ReactNode,
} from "react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";

interface PopoverProps {
    label: string;
    trigger: ReactNode;
    children: ReactNode | ((controls: { close: () => void }) => ReactNode);
    align?: "start" | "end";
    className?: string;
    triggerClassName?: string;
    width?: number;
    onOpenChange?: (isOpen: boolean) => void;
    disabled?: boolean;
}

/**
 * Компактная floating surface для вторичных инструментов. Закрывается по
 * Escape/клику снаружи и возвращает фокус на trigger.
 */
export function Popover({
    label,
    trigger,
    children,
    align = "end",
    className,
    triggerClassName,
    width: panelWidth = 288,
    onOpenChange,
    disabled = false,
}: PopoverProps) {
    const [isOpen, setOpen] = useState(false);
    const id = useId();
    const rootRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const panelRef = useRef<HTMLDivElement>(null);
    const [position, setPosition] = useState<{ left: number; top: number; width: number } | null>(
        null,
    );

    useLayoutEffect(() => {
        if (!isOpen) return;
        const updatePosition = () => {
            const triggerElement = triggerRef.current;
            const panelElement = panelRef.current;
            if (!triggerElement || !panelElement) return;
            const triggerRect = triggerElement.getBoundingClientRect();
            const margin = 12;
            const width = Math.min(panelWidth, window.innerWidth - margin * 2);
            const preferredLeft =
                align === "end" ? triggerRect.right - width : triggerRect.left;
            const left = Math.max(
                margin,
                Math.min(preferredLeft, window.innerWidth - width - margin),
            );
            const below = triggerRect.bottom + 6;
            const above = triggerRect.top - panelElement.offsetHeight - 6;
            const top =
                below + panelElement.offsetHeight <= window.innerHeight - margin || above < margin
                    ? below
                    : above;
            setPosition({ left, top, width });
        };
        updatePosition();
        window.addEventListener("resize", updatePosition);
        window.addEventListener("scroll", updatePosition, true);
        return () => {
            window.removeEventListener("resize", updatePosition);
            window.removeEventListener("scroll", updatePosition, true);
        };
    }, [align, isOpen, panelWidth]);

    const changeOpen = useCallback((open: boolean) => {
        setOpen(open);
        onOpenChange?.(open);
    }, [onOpenChange]);

    const close = () => {
        changeOpen(false);
        window.requestAnimationFrame(() => {
            document.getElementById(`${id}-trigger`)?.focus();
        });
    };

    useEffect(() => {
        if (!isOpen) return;

        const frame = window.requestAnimationFrame(() => {
            panelRef.current
                ?.querySelector<HTMLElement>(
                    "input:not([disabled]), select:not([disabled]), button:not([disabled]), [tabindex='0']",
                )
                ?.focus();
        });
        const onPointerDown = (event: PointerEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) changeOpen(false);
        };
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                event.preventDefault();
                changeOpen(false);
                triggerRef.current?.focus();
            }
        };
        window.addEventListener("pointerdown", onPointerDown);
        window.addEventListener("keydown", onKeyDown);
        return () => {
            window.cancelAnimationFrame(frame);
            window.removeEventListener("pointerdown", onPointerDown);
            window.removeEventListener("keydown", onKeyDown);
        };
    }, [changeOpen, isOpen]);

    return (
        <div ref={rootRef} className="relative">
            <Button
                ref={triggerRef}
                id={`${id}-trigger`}
                size="sm"
                aria-haspopup="dialog"
                aria-label={label}
                aria-expanded={isOpen}
                aria-controls={isOpen ? id : undefined}
                disabled={disabled}
                className={triggerClassName}
                onClick={() => changeOpen(!isOpen)}
            >
                {trigger}
            </Button>
            {isOpen && (
                <div
                    ref={panelRef}
                    id={id}
                    role="dialog"
                    aria-label={label}
                    style={position ?? { visibility: "hidden" }}
                    className={cn(
                        "material-glass fixed z-[60]",
                        "rounded-[var(--radius-panel)] p-3 shadow-panel",
                        className,
                    )}
                >
                    {typeof children === "function" ? children({ close }) : children}
                </div>
            )}
        </div>
    );
}
