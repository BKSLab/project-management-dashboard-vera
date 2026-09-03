import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Dialog, Heading, Modal as RACModal, ModalOverlay } from "react-aria-components";
import { cn } from "@/lib/cn";
import { IconButton } from "@/components/ui/Button";

interface ModalProps {
    title: string;
    description?: string;
    children: ReactNode;
    footer?: ReactNode;
    isOpen?: boolean;
    onOpenChange?: (isOpen: boolean) => void;
    /** Ширина диалога: обычные формы — sm, карточка задачи — lg. */
    size?: "sm" | "md" | "lg";
    isDismissable?: boolean;
    tall?: boolean;
}

const SIZES = {
    sm: "max-w-md",
    md: "max-w-xl",
    lg: "max-w-3xl",
} as const;

export function Modal({
    title,
    description,
    children,
    footer,
    isOpen,
    onOpenChange,
    size = "sm",
    isDismissable = true,
    tall = false,
}: ModalProps) {
    return (
        <ModalOverlay
            isOpen={isOpen}
            onOpenChange={onOpenChange}
            isDismissable={isDismissable}
            className={cn(
                "modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4",
                "backdrop-blur-[1.5px]",
            )}
        >
            <RACModal
                className={cn(
                    "modal-surface material-glass relative flex w-full flex-col overflow-hidden",
                    tall ? "max-h-[min(92vh,1000px)]" : "max-h-[min(85vh,900px)]",
                    "rounded-[var(--radius-floating)] shadow-panel",
                    SIZES[size],
                )}
            >
                <Dialog aria-label={title} className="flex min-h-0 flex-1 flex-col outline-none">
                    {({ close }) => (
                        <>
                            <header className="flex shrink-0 items-start justify-between gap-4 border-b border-line-subtle bg-floating/45 px-5 py-4">
                                <div className="flex min-w-0 flex-col gap-1">
                                    <Heading
                                        slot="title"
                                        className="min-w-0 text-[15px] font-semibold break-words text-primary"
                                    >
                                        {title}
                                    </Heading>
                                    {description && (
                                        <p className="text-[13px] text-muted">{description}</p>
                                    )}
                                </div>
                                <IconButton label="Закрыть" onClick={close}>
                                    <X size={16} aria-hidden="true" />
                                </IconButton>
                            </header>

                            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-5">
                                {children}
                            </div>

                            {footer && (
                                <footer className="flex shrink-0 items-center justify-end gap-2 border-t border-line-subtle bg-floating/35 px-5 py-3.5">
                                    {footer}
                                </footer>
                            )}
                        </>
                    )}
                </Dialog>
            </RACModal>
        </ModalOverlay>
    );
}
