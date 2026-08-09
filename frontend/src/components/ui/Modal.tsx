import type { DialogProps } from "react-aria-components";
import { Modal as RACModal, ModalOverlay, Dialog, Heading } from "react-aria-components";
import { cn } from "@/lib/cn";

interface ModalProps extends DialogProps {
    title?: string;
    children: React.ReactNode;
    isOpen?: boolean;
    onOpenChange?: (isOpen: boolean) => void;
    containerClassName?: string;
    overlayClassName?: string;
}

export function Modal({
    title,
    children,
    isOpen,
    onOpenChange,
    containerClassName,
    overlayClassName,
    ...props
}: ModalProps) {
    return (
        <ModalOverlay
            isOpen={isOpen}
            onOpenChange={onOpenChange}
            isDismissable
            className={cn(
                "fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md",
                overlayClassName,
            )}
        >
            <RACModal
                className={cn(
                    "relative flex w-full max-w-md flex-col overflow-hidden rounded-2xl",
                    "border border-white/15",
                    "bg-[linear-gradient(160deg,rgba(255,255,255,0.07),rgba(255,255,255,0.03))]",
                    "shadow-[0_24px_64px_rgba(0,0,0,0.65),inset_0_0_0_1px_rgba(255,255,255,0.05)]",
                    "backdrop-blur-md backdrop-saturate-150",
                    containerClassName
                )}
            >
                <Dialog {...props} className="flex min-h-0 flex-1 flex-col outline-none">
                    {({ close }) => (
                        <>
                            <div
                                aria-hidden="true"
                                className="h-px shrink-0 bg-gradient-to-r from-transparent via-accent to-transparent"
                            />

                            <div className="flex min-h-0 flex-1 flex-col p-6">
                                {title && (
                                    <div className="mb-5 flex shrink-0 items-center justify-between gap-4">
                                        <Heading
                                            slot="title"
                                            className="min-w-0 break-words text-xl font-bold text-foreground"
                                        >
                                            {title}
                                        </Heading>
                                        <button
                                            onClick={close}
                                            aria-label="Закрыть"
                                            className="shrink-0 rounded-lg p-1.5 text-muted transition-colors hover:bg-white/10 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                                        >
                                            <svg
                                                width="16"
                                                height="16"
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="currentColor"
                                                strokeWidth="2.5"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                aria-hidden="true"
                                            >
                                                <path d="M18 6L6 18M6 6l12 12" />
                                            </svg>
                                        </button>
                                    </div>
                                )}
                                <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
                                    {children}
                                </div>
                            </div>

                            <div
                                aria-hidden="true"
                                className="h-px shrink-0 bg-gradient-to-r from-transparent via-white/8 to-transparent"
                            />
                        </>
                    )}
                </Dialog>
            </RACModal>
        </ModalOverlay>
    );
}
