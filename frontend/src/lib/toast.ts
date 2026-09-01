import { create } from "zustand";

export type ToastTone = "success" | "error";

export interface Toast {
    id: number;
    tone: ToastTone;
    message: string;
}

interface ToastState {
    toasts: Toast[];
    push: (tone: ToastTone, message: string) => void;
    dismiss: (id: number) => void;
}

let nextToastId = 1;

export const useToastStore = create<ToastState>((set) => ({
    toasts: [],
    push: (tone, message) =>
        set((state) => ({ toasts: [...state.toasts, { id: nextToastId++, tone, message }] })),
    dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}));

/** Сообщает об исходе оптимистичной операции — например, откате drag & drop. */
export function useToast() {
    const push = useToastStore((state) => state.push);
    return {
        success: (message: string) => push("success", message),
        error: (message: string) => push("error", message),
    };
}
