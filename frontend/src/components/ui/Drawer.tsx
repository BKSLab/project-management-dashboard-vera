import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Dialog, Modal as RACModal, ModalOverlay } from "react-aria-components";
import { cn } from "@/lib/cn";
import { IconButton } from "@/components/ui/Button";

interface DrawerProps {
    /** Доступное имя панели: у неё нет одного короткого заголовка. */
    label: string;
    header: ReactNode;
    children: ReactNode;
    footer?: ReactNode;
    isOpen: boolean;
    onClose: () => void;
}

/**
 * Правая панель деталей: рабочая область остаётся видимой, поэтому контекст
 * доски или карты не теряется (раздел 11). На узких экранах разворачивается
 * в полноэкранный лист (раздел 19).
 */
export function Drawer({ label, header, children, footer, isOpen, onClose }: DrawerProps) {
    return (
        <ModalOverlay
            isOpen={isOpen}
            onOpenChange={(open) => {
                if (!open) {
                    onClose();
                }
            }}
            isDismissable
            className="fixed inset-0 z-50 flex justify-end bg-black/45"
        >
            <RACModal
                className={cn(
                    "glass flex h-full w-full flex-col overflow-hidden shadow-panel",
                    "sm:w-[min(560px,100vw)] sm:border-l sm:border-line",
                )}
            >
                <Dialog aria-label={label} className="flex min-h-0 flex-1 flex-col outline-none">
                    <header className="flex shrink-0 items-start gap-3 border-b border-line px-4 py-3">
                        <div className="min-w-0 flex-1">{header}</div>
                        <IconButton label="Закрыть панель задачи" onClick={onClose}>
                            <X size={16} aria-hidden="true" />
                        </IconButton>
                    </header>

                    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">{children}</div>

                    {footer && (
                        <footer className="flex shrink-0 items-center justify-between gap-2 border-t border-line px-4 py-3">
                            {footer}
                        </footer>
                    )}
                </Dialog>
            </RACModal>
        </ModalOverlay>
    );
}

interface DrawerSectionProps {
    title: string;
    count?: number | null;
    action?: ReactNode;
    children: ReactNode;
}

export function DrawerSection({ title, count, action, children }: DrawerSectionProps) {
    return (
        <section className="border-b border-line-subtle px-4 py-4 last:border-b-0">
            <div className="mb-2.5 flex items-center justify-between gap-2">
                <h3 className="flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
                    {title}
                    {typeof count === "number" && (
                        <span className="font-mono text-[11px] text-disabled">{count}</span>
                    )}
                </h3>
                {action}
            </div>
            {children}
        </section>
    );
}
