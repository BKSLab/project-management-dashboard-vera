import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { CircleHelp } from "lucide-react";

interface HelpHintProps {
    /** О чём подсказка — доступное имя кнопки: «Что значит режим распределения». */
    label: string;
    children: ReactNode;
    /** Короткий текст для подсказки при наведении; по умолчанию — label. */
    title?: string;
}

/**
 * Кнопка «?» рядом с неочевидным полем: при наведении — короткая подсказка,
 * по нажатию — пояснение в маленьком окне (работает и на телефоне).
 */
export function HelpHint({ label, children, title }: HelpHintProps) {
    const id = useId();
    const [isOpen, setOpen] = useState(false);
    const rootRef = useRef<HTMLSpanElement>(null);
    const buttonRef = useRef<HTMLButtonElement>(null);
    const panelRef = useRef<HTMLSpanElement>(null);
    const [position, setPosition] = useState<{ left: number; top: number } | null>(null);

    // Окно подсказки — fixed по координатам кнопки: иначе его обрезает прокрутка листа или панели.
    useLayoutEffect(() => {
        if (!isOpen) return;
        const place = () => {
            const button = buttonRef.current?.getBoundingClientRect();
            const panel = panelRef.current;
            if (!button || !panel) return;
            const margin = 12;
            const left = Math.max(margin, Math.min(button.left, window.innerWidth - panel.offsetWidth - margin));
            const below = button.bottom + 6;
            const top = below + panel.offsetHeight <= window.innerHeight - margin ? below : Math.max(margin, button.top - panel.offsetHeight - 6);
            setPosition({ left, top });
        };
        place();
        window.addEventListener("resize", place);
        window.addEventListener("scroll", place, true);
        return () => {
            window.removeEventListener("resize", place);
            window.removeEventListener("scroll", place, true);
        };
    }, [isOpen]);

    useEffect(() => {
        if (!isOpen) return;
        const close = (event: PointerEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
        };
        const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
        window.addEventListener("pointerdown", close);
        window.addEventListener("keydown", onKey);
        return () => {
            window.removeEventListener("pointerdown", close);
            window.removeEventListener("keydown", onKey);
        };
    }, [isOpen]);

    return (
        <span ref={rootRef} className="relative inline-flex align-middle">
            <button
                ref={buttonRef}
                type="button"
                className="grid size-5 place-items-center rounded-full text-muted hover:bg-hover hover:text-primary"
                aria-label={label}
                aria-expanded={isOpen}
                aria-controls={isOpen ? id : undefined}
                title={title ?? label}
                onClick={() => setOpen((open) => !open)}
            >
                <CircleHelp size={14} strokeWidth={2} aria-hidden="true" />
            </button>
            {isOpen && (
                <span
                    ref={panelRef}
                    id={id}
                    role="note"
                    style={position ?? { visibility: "hidden", left: 0, top: 0 }}
                    className="material-glass fixed z-[120] block w-72 max-w-[80vw] rounded-[var(--radius-panel)] p-3 text-[12px] leading-snug font-normal tracking-normal normal-case text-secondary shadow-panel"
                >
                    {children}
                </span>
            )}
        </span>
    );
}
