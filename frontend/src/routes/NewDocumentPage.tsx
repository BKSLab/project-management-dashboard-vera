import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DocumentDetail } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Button } from "@/components/ui/Button";
import { MarkdownEditor } from "@/components/docs/MarkdownEditor";

export function NewDocumentPage() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [searchParams] = useSearchParams();
    const returnToTask = searchParams.get("returnToTask");

    const [title, setTitle] = useState("");
    const [content, setContent] = useState("");

    const backTarget = returnToTask ? `/kanban?highlight=${returnToTask}` : "/docs";

    const createMutation = useMutation({
        mutationFn: () => api.post<DocumentDetail>("/api/documents", { title: title.trim(), content_md: content }),
        onSuccess: async (created) => {
            queryClient.invalidateQueries({ queryKey: ["documents"] });
            if (returnToTask) {
                const taskId = Number(returnToTask);
                await api.post("/api/document-links", { document_id: created.id, kanban_task_id: taskId });
                queryClient.invalidateQueries({ queryKey: ["kanban", "tasks", taskId, "links"] });
                navigate(`/kanban?highlight=${taskId}`);
            } else {
                navigate(`/docs/${created.slug}`);
            }
        },
    });

    return (
        <div className="mx-auto max-w-6xl">
            <div className="mb-6 flex items-center justify-between gap-4">
                <FocusHeading className="text-2xl font-bold">Новый документ</FocusHeading>
                <Link to={backTarget} className="text-sm text-muted hover:text-foreground">
                    ← Отмена
                </Link>
            </div>

            {createMutation.isError && (
                <div className="mb-4">
                    <ErrorMessage message={(createMutation.error as Error).message} />
                </div>
            )}

            <label htmlFor="new-document-title" className="mb-2 block text-sm font-semibold text-muted">
                Заголовок
            </label>
            <input
                id="new-document-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Заголовок документа..."
                autoFocus
                className="mb-4 w-full rounded border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            />

            <MarkdownEditor value={content} onChange={setContent} />

            <div className="mt-4 flex gap-2">
                <Button
                    variant="primary"
                    disabled={!title.trim() || createMutation.isPending}
                    onClick={() => createMutation.mutate()}
                >
                    {createMutation.isPending ? "Сохранение..." : "Сохранить"}
                </Button>
                <Button variant="neutral" onClick={() => navigate(backTarget)}>
                    Отмена
                </Button>
            </div>
        </div>
    );
}
