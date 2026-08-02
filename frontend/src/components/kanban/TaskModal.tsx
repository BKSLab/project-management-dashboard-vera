import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DocumentListItem, KanbanTask, LinkedDocument, TaskActivity, TaskComment } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Modal } from "@/components/ui/Modal";

interface TaskModalProps {
    task: KanbanTask;
    onClose: () => void;
}

const EVENT_LABELS: Record<TaskActivity["event_type"], string> = {
    STAGE_CHANGED: "Стадия изменена",
    DUE_DATE_CHANGED: "Срок изменён",
    DESCRIPTION_CHANGED: "Описание изменено",
    COMMENT_ADDED: "Добавлен комментарий",
};

export function TaskModal({ task, onClose }: TaskModalProps) {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [isEditingDescription, setIsEditingDescription] = useState(false);
    const [descriptionDraft, setDescriptionDraft] = useState(task.description_md ?? "");
    const [commentDraft, setCommentDraft] = useState("");
    const [authorDraft, setAuthorDraft] = useState("");
    const [selectedDocId, setSelectedDocId] = useState("");

    const invalidateTask = () => {
        queryClient.invalidateQueries({ queryKey: ["kanban", "tasks"] });
        queryClient.invalidateQueries({ queryKey: ["kanban", "tasks", task.id, "activity"] });
        queryClient.invalidateQueries({ queryKey: ["wbs", "tree"] });
    };

    const updateMutation = useMutation({
        mutationFn: (data: Partial<Pick<KanbanTask, "description_md" | "due_date">>) =>
            api.patch<KanbanTask>(`/api/v1/kanban/tasks/${task.id}`, data),
        onSuccess: () => {
            invalidateTask();
            setIsEditingDescription(false);
        },
    });

    const commentsQuery = useQuery({
        queryKey: ["kanban", "tasks", task.id, "comments"],
        queryFn: () => api.get<TaskComment[]>(`/api/v1/kanban/tasks/${task.id}/comments`),
    });

    const activityQuery = useQuery({
        queryKey: ["kanban", "tasks", task.id, "activity"],
        queryFn: () => api.get<TaskActivity[]>(`/api/v1/kanban/tasks/${task.id}/activity`),
    });

    const linksQuery = useQuery({
        queryKey: ["kanban", "tasks", task.id, "links"],
        queryFn: () => api.get<LinkedDocument[]>(`/api/v1/kanban/tasks/${task.id}/links`),
    });

    const documentsQuery = useQuery({
        queryKey: ["documents"],
        queryFn: () => api.get<DocumentListItem[]>("/api/v1/documents"),
    });

    const unlinkedDocuments = useMemo(() => {
        const linkedIds = new Set((linksQuery.data ?? []).map((link) => link.document_id));
        return (documentsQuery.data ?? []).filter((document) => !linkedIds.has(document.id));
    }, [documentsQuery.data, linksQuery.data]);

    const invalidateLinks = () => {
        queryClient.invalidateQueries({ queryKey: ["kanban", "tasks", task.id, "links"] });
    };

    const linkMutation = useMutation({
        mutationFn: (documentId: number) =>
            api.post("/api/v1/document-links", { document_id: documentId, kanban_task_id: task.id }),
        onSuccess: () => {
            setSelectedDocId("");
            invalidateLinks();
        },
    });

    const unlinkMutation = useMutation({
        mutationFn: (linkId: number) => api.delete(`/api/v1/document-links/${linkId}`),
        onSuccess: invalidateLinks,
    });

    const addCommentMutation = useMutation({
        mutationFn: () =>
            api.post<TaskComment>(`/api/v1/kanban/tasks/${task.id}/comments`, {
                author_name: authorDraft || undefined,
                body_md: commentDraft,
            }),
        onSuccess: () => {
            setCommentDraft("");
            queryClient.invalidateQueries({ queryKey: ["kanban", "tasks", task.id, "comments"] });
            queryClient.invalidateQueries({ queryKey: ["kanban", "tasks", task.id, "activity"] });
            queryClient.invalidateQueries({ queryKey: ["kanban", "tasks"] });
        },
    });

    const mutationError =
        updateMutation.error ??
        linkMutation.error ??
        unlinkMutation.error ??
        addCommentMutation.error;

    return (
        <Modal
            title={task.title}
            isOpen
            onOpenChange={(isOpen) => {
                if (!isOpen) onClose();
            }}
            containerClassName="scrollbar-thin max-h-[calc(100dvh-2rem)] max-w-3xl overflow-x-hidden overflow-y-auto bg-surface/95"
        >
                <p className="mb-3 font-mono text-xs text-muted">TASK-{task.id}</p>

                {mutationError && (
                    <div className="mb-4">
                        <ErrorMessage message={(mutationError as Error).message} />
                    </div>
                )}

                {task.wbs_item_id !== null && (
                    <Link to="/wbs" className="mb-4 inline-block text-sm text-accent hover:underline">
                        Открыть в ИСР →
                    </Link>
                )}

                <section className="mb-4 rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
                    <div className="mb-2 flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-muted">Описание</h3>
                        {!isEditingDescription && (
                            <Button
                                variant="neutral"
                                onClick={() => {
                                    setDescriptionDraft(task.description_md ?? "");
                                    setIsEditingDescription(true);
                                }}
                            >
                                Редактировать
                            </Button>
                        )}
                    </div>
                    {isEditingDescription ? (
                        <div>
                            <textarea
                                value={descriptionDraft}
                                onChange={(event) => setDescriptionDraft(event.target.value)}
                                rows={6}
                                placeholder="Описание задачи..."
                                className="w-full resize-none rounded border border-border bg-surface p-3 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                            />
                            <div className="mt-2 flex gap-2">
                                <Button
                                    variant="primary"
                                    disabled={updateMutation.isPending}
                                    onClick={() => updateMutation.mutate({ description_md: descriptionDraft })}
                                >
                                    Сохранить
                                </Button>
                                <Button variant="neutral" onClick={() => setIsEditingDescription(false)}>
                                    Отмена
                                </Button>
                            </div>
                        </div>
                    ) : task.description_md ? (
                        <p className="whitespace-pre-wrap text-sm text-foreground">{task.description_md}</p>
                    ) : (
                        <p className="text-sm text-muted">Описание не задано.</p>
                    )}
                </section>

                <section className="mb-4 rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
                    <h3 className="mb-2 text-sm font-semibold text-muted">Срок</h3>
                    <input
                        type="date"
                        value={task.due_date ?? ""}
                        onChange={(event) =>
                            updateMutation.mutate({ due_date: event.target.value || null })
                        }
                        className="rounded border border-border bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    />
                </section>

                <section className="mb-4 rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
                    <h3 className="mb-2 text-sm font-semibold text-muted">
                        Связанные документы
                    </h3>
                    {linksQuery.data && linksQuery.data.length > 0 ? (
                        <ul className="mb-3 space-y-1">
                            {linksQuery.data.map((link) => (
                                <li key={link.link_id} className="flex items-center justify-between gap-2">
                                    <Link to={`/docs/${link.slug}`} className="text-sm text-accent hover:underline">
                                        {link.title}
                                    </Link>
                                    <button
                                        onClick={() => unlinkMutation.mutate(link.link_id)}
                                        aria-label={`Отвязать документ «${link.title}»`}
                                        title="Отвязать"
                                        className="shrink-0 rounded p-1 text-muted hover:bg-danger/10 hover:text-danger focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                                    >
                                        ✕
                                    </button>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="mb-3 text-sm text-muted">Связанных документов нет.</p>
                    )}

                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <select
                            value={selectedDocId}
                            onChange={(event) => setSelectedDocId(event.target.value)}
                            className="min-w-0 flex-1 basis-48 rounded border border-border bg-surface px-2 py-1.5 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        >
                            <option value="">Выбрать документ...</option>
                            {unlinkedDocuments.map((document) => (
                                <option key={document.id} value={document.id}>
                                    {document.title}
                                </option>
                            ))}
                        </select>
                        <Button
                            variant="secondary"
                            disabled={!selectedDocId || linkMutation.isPending}
                            onClick={() => linkMutation.mutate(Number(selectedDocId))}
                        >
                            Привязать
                        </Button>
                        <Button
                            variant="neutral"
                            onClick={() => navigate(`/docs/new?returnToTask=${task.id}`)}
                        >
                            + Новый документ
                        </Button>
                    </div>
                </section>

                <section className="mb-4 rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
                    <h3 className="mb-2 text-sm font-semibold text-muted">Комментарии</h3>
                    {commentsQuery.isPending && <Spinner />}
                    <ul className="mb-3 space-y-2">
                        {commentsQuery.data?.map((comment) => (
                            <li key={comment.id} className="rounded-xl bg-white/[0.04] p-3 text-sm">
                                <p className="mb-1 text-xs font-semibold text-accent-secondary">
                                    {comment.author_name ?? "Без подписи"}{" "}
                                    <span className="font-normal text-muted">
                                        · {new Date(comment.created_at).toLocaleString("ru-RU")}
                                    </span>
                                </p>
                                <p className="text-foreground">{comment.body_md}</p>
                            </li>
                        ))}
                    </ul>
                    <div className="space-y-2">
                        <input
                            value={authorDraft}
                            onChange={(event) => setAuthorDraft(event.target.value)}
                            placeholder="Имя (опционально)"
                            className="w-full rounded border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        />
                        <textarea
                            value={commentDraft}
                            onChange={(event) => setCommentDraft(event.target.value)}
                            placeholder="Текст комментария..."
                            className="w-full resize-none rounded border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                            rows={3}
                        />
                        <Button
                            variant="secondary"
                            disabled={!commentDraft.trim() || addCommentMutation.isPending}
                            onClick={() => addCommentMutation.mutate()}
                        >
                            Добавить комментарий
                        </Button>
                    </div>
                </section>

                <section className="rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
                    <h3 className="mb-2 text-sm font-semibold text-muted">История</h3>
                    {activityQuery.isPending && <Spinner />}
                    <ul className="space-y-1">
                        {activityQuery.data?.map((activity) => (
                            <li key={activity.id} className="text-xs text-muted">
                                <span className="text-foreground">{EVENT_LABELS[activity.event_type]}</span>
                                {activity.from_value && activity.to_value && (
                                    <span> — {activity.from_value} → {activity.to_value}</span>
                                )}
                                {" · "}
                                {new Date(activity.created_at).toLocaleString("ru-RU")}
                            </li>
                        ))}
                    </ul>
                </section>
        </Modal>
    );
}
