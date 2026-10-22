import { useEffect, useRef, type RefObject } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { attentionKey, type TaskViewToken } from "@/lib/taskAttention";
import { useCurrentUser } from "@/lib/useAuth";
import { useToastStore } from "@/lib/toast";

/** Просмотр подтверждается только после успешной загрузки видимой карточки. */
export function useTaskViewed(taskId: number, view: TaskViewToken | undefined, element: RefObject<HTMLElement | null>) {
    const { data: user } = useCurrentUser();
    const client = useQueryClient();
    const acknowledged = useRef("");
    useEffect(() => {
        const node = element.current;
        if (!view || !node || !user) return;
        const signature = `${user.id}:${taskId}:${view.revision}:${view.deadline_revision}:${view.overdue}`;
        if (acknowledged.current === signature) return;
        let intersecting = false;
        let submitting = false;
        let disposed = false;
        const confirm = () => {
            if (disposed || submitting || !intersecting || document.visibilityState !== "visible") return;
            submitting = true;
            void api.post(`/api/v1/tasks/${taskId}/view`, view).then(() => {
                acknowledged.current = signature;
                void client.invalidateQueries({ queryKey: attentionKey(user.id) });
            }).catch(() => {
                if (!disposed) useToastStore.getState().push("error", "Не удалось сохранить просмотр задачи. Счётчик пока не сброшен.");
            });
        };
        const observer = new IntersectionObserver(entries => {
            intersecting = entries.some(entry => entry.isIntersecting);
            confirm();
        });
        observer.observe(node);
        document.addEventListener("visibilitychange", confirm);
        return () => { disposed = true; observer.disconnect(); document.removeEventListener("visibilitychange", confirm); };
    }, [taskId, view, user, client, element]);
}
