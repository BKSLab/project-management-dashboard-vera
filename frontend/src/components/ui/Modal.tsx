import type { DialogProps } from "react-aria-components";
import { Modal as RACModal, Dialog, Heading } from "react-aria-components";
import { cn } from "@/lib/cn";

interface ModalProps extends DialogProps {
    title?: string;
    children: React.ReactNode;
    isOpen?: boolean;
    onOpenChange?: (isOpen: boolean) => void;
    containerClassName?: string;
}

export function Modal({
    title,
    children,
    isOpen,
    onOpenChange,
    containerClassName,
    ...props
}: ModalProps) {
    return (
        <RACModal
            isOpen={isOpen}
            onOpenChange={onOpenChange}
            isDismissable
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md"
        >
            <Dialog
                {...props}
                className={cn(
                    "relative w-full max-w-md overflow-hidden rounded-2xl",
                    "border border-white/15",
                    "bg-[linear-gradient(160deg,rgba(255,255,255,0.07),rgba(255,255,255,0.03))]",
                    "shadow-[0_24px_64px_rgba(0,0,0,0.65),inset_0_0_0_1px_rgba(255,255,255,0.05)]",
                    "backdrop-blur-md backdrop-saturate-150",
                    containerClassName
                )}
            >
                {({ close }) => (
                    <>
                        <div
                            aria-hidden="true"
                            className="h-px bg-gradient-to-r from-transparent via-accent to-transparent"
                        />

                        <div className="p-6">
                            {title && (
                                <div className="mb-5 flex items-center justify-between gap-4">
                                    <Heading
                                        slot="title"
                                        className="text-xl font-bold text-foreground"
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
                            {children}
                        </div>

                        <div
                            aria-hidden="true"
                            className="h-px bg-gradient-to-r from-transparent via-white/8 to-transparent"
                        />
                    </>
                )}
            </Dialog>
        </RACModal>
    );
}
