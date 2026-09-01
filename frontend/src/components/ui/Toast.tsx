import { useEffect } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { useToastStore, type Toast, type ToastTone } from "@/lib/toast";
import { IconButton } from "@/components/ui/Button";

const TONE_CLASSES: Record<ToastTone, string> = {
    success: "border-success/30 text-success",
    error: "border-danger/30 text-danger",
};

function ToastItem({ toast }: { toast: Toast }) {
    const dismiss = useToastStore((state) => state.dismiss);

    useEffect(() => {
        const timer = window.setTimeout(() => dismiss(toast.id), 5000);
        return () => window.clearTimeout(timer);
    }, [toast.id, dismiss]);

    return (
        <div
            className={cn(
                "glass flex items-start gap-2.5 rounded-md border px-3 py-2.5 shadow-panel",
                TONE_CLASSES[toast.tone],
            )}
        >
            {toast.tone === "success" ? (
                <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            ) : (
                <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            )}
            <p className="min-w-0 flex-1 text-[13px] break-words text-secondary">{toast.message}</p>
            <IconButton label="Скрыть уведомление" size="sm" onClick={() => dismiss(toast.id)}>
                <X size={12} aria-hidden="true" />
            </IconButton>
        </div>
    );
}

export function ToastViewport() {
    const toasts = useToastStore((state) => state.toasts);
    return (
        <div
            aria-live="polite"
            aria-atomic="false"
            className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-80 flex-col gap-2"
        >
            {toasts.map((toast) => (
                <div key={toast.id} className="pointer-events-auto">
                    <ToastItem toast={toast} />
                </div>
            ))}
        </div>
    );
}
