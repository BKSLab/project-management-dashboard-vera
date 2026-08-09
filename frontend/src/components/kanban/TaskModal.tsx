import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiUrl } from "@/lib/api";
import { cn } from "@/lib/cn";
import type {
    DocumentListItem,
    KanbanStage,
    KanbanTask,
    LinkedDocument,
    TaskActivity,
    TaskAttachment,
    TaskComment,
} from "@/lib/types";
import type { FileDescriptor } from "@/lib/files";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Modal } from "@/components/ui/Modal";
import { FileList } from "@/components/files/FileList";
import { FileUploadControl } from "@/components/files/FileUploadControl";

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

type TaskSection = "description" | "comments" | "files" | "documents" | "history";

function AttachmentsSkeleton() {
    return (
        <div role="status" aria-live="polite" aria-label="Загрузка файлов..." className="flex flex-wrap gap-2">
            {Array.from({ length: 3 }).map((_, index) => (
                <div
                    key={index}
                    className="flex w-[220px] max-w-full items-center gap-2.5 rounded-xl border border-white/[0.07] bg-surface p-2"
                >
                    <Skeleton className="h-11 w-11 shrink-0 rounded-lg" />
                    <div className="min-w-0 flex-1 space-y-1.5">
                        <Skeleton className="h-3 w-4/5" />
                        <Skeleton className="h-2.5 w-1/3" />
                    </div>
                </div>
            ))}
        </div>
    );
}

function CommentsSkeleton() {
    return (
        <ul role="status" aria-live="polite" aria-label="Загрузка комментариев..." className="mb-3 space-y-2">
            {Array.from({ length: 3 }).map((_, index) => (
                <li key={index} className="space-y-2 rounded-xl bg-white/[0.04] p-3">
                    <Skeleton className="h-3 w-32" />
                    <Skeleton className="h-3 w-full" />
                    <Skeleton className="h-3 w-2/3" />
                </li>
            ))}
        </ul>
    );
}

function HistorySkeleton() {
    return (
        <ul role="status" aria-live="polite" aria-label="Загрузка истории..." className="space-y-1">
            {Array.from({ length: 4 }).map((_, index) => (
                <li key={index}>
                    <Skeleton className="h-3 w-4/5" />
                </li>
            ))}
        </ul>
    );
}

export function TaskModal({ task, onClose }: TaskModalProps) {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const attachmentSectionRef = useRef<HTMLElement>(null);
    const [activeSection, setActiveSection] = useState<TaskSection>("description");
    const [isEditingDescription, setIsEditingDescription] = useState(false);
    const [descriptionDraft, setDescriptionDraft] = useState(task.description_md ?? "");
    const [commentDraft, setCommentDraft] = useState("");
    const [authorDraft, setAuthorDraft] = useState("");
    const [selectedDocId, setSelectedDocId] = useState("");
    const [attachmentError, setAttachmentError] = useState<string | null>(null);

    const stagesQuery = useQuery({
        queryKey: ["kanban", "stages"],
        queryFn: () => api.get<KanbanStage[]>("/api/v1/kanban/stages"),
    });

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

    const moveMutation = useMutation({
        mutationFn: (stageId: number) =>
            api.patch<KanbanTask>(`/api/v1/kanban/tasks/${task.id}/move`, {
                stage_id: stageId,
            }),
        onSuccess: (movedTask) => {
            queryClient.setQueryData(
                ["kanban", "tasks", "detail", task.id],
                movedTask,
            );
            invalidateTask();
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

    const attachmentsQuery = useQuery({
        queryKey: ["kanban", "tasks", task.id, "attachments"],
        queryFn: () => api.get<TaskAttachment[]>(`/api/v1/kanban/tasks/${task.id}/attachments`),
    });

    const attachmentFiles = useMemo<FileDescriptor[]>(() => (
        (attachmentsQuery.data ?? []).map((attachment) => ({
            key: String(attachment.id),
            name: attachment.original_name,
            url: apiUrl(attachment.content_url),
            size: attachment.size,
            mime: attachment.content_type,
            previewable: attachment.previewable,
        }))
    ), [attachmentsQuery.data]);

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

    const uploadAttachmentMutation = useMutation({
        mutationFn: async (files: File[]) => {
            const uploaded: TaskAttachment[] = [];
            for (const file of files) {
                const body = new FormData();
                body.append("file", file);
                uploaded.push(await api.postForm<TaskAttachment>(
                    `/api/v1/kanban/tasks/${task.id}/attachments`,
                    body,
                ));
            }
            return uploaded;
        },
        onMutate: () => setAttachmentError(null),
        onError: (error) => setAttachmentError((error as Error).message),
        onSettled: () => {
            queryClient.invalidateQueries({
                queryKey: ["kanban", "tasks", task.id, "attachments"],
            });
        },
    });

    const deleteAttachmentMutation = useMutation({
        mutationFn: (attachmentId: number) =>
            api.delete(`/api/v1/kanban/tasks/${task.id}/attachments/${attachmentId}`),
        onMutate: () => setAttachmentError(null),
        onError: (error) => setAttachmentError((error as Error).message),
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["kanban", "tasks", task.id, "attachments"],
            });
        },
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
        moveMutation.error ??
        linkMutation.error ??
        unlinkMutation.error ??
        addCommentMutation.error;

    const navItems: { key: TaskSection; label: string; count: number | null }[] = [
        { key: "description", label: "Описание", count: null },
        { key: "comments", label: "Комментарии", count: commentsQuery.data?.length ?? null },
        { key: "files", label: "Файлы", count: attachmentsQuery.data?.length ?? null },
        { key: "documents", label: "Документы", count: linksQuery.data?.length ?? null },
        { key: "history", label: "История", count: activityQuery.data?.length ?? null },
    ];

    return (
        <Modal
            title={task.title}
            isOpen
            onOpenChange={(isOpen) => {
                if (!isOpen) onClose();
            }}
            containerClassName="scrollbar-thin max-h-[calc(100dvh-2rem)] w-full max-w-4xl overflow-x-hidden overflow-y-auto bg-surface/95"
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

                <section className="mb-4 grid gap-4 rounded-xl border border-white/[0.05] bg-surface-elevated p-4 sm:grid-cols-2">
                    <div>
                        <label
                            htmlFor={`task-stage-${task.id}`}
                            className="mb-2 block text-sm font-semibold text-muted"
                        >
                            Стадия
                        </label>
                        <select
                            id={`task-stage-${task.id}`}
                            value={task.stage_id}
                            disabled={stagesQuery.isPending || stagesQuery.isError || moveMutation.isPending}
                            aria-busy={moveMutation.isPending}
                            onChange={(event) => {
                                const stageId = Number(event.target.value);
                                if (stageId !== task.stage_id) moveMutation.mutate(stageId);
                            }}
                            className="w-full rounded border border-border bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {stagesQuery.data?.map((stage) => (
                                <option key={stage.id} value={stage.id}>
                                    {stage.name}
                                </option>
                            ))}
                        </select>
                        {stagesQuery.isError && (
                            <p className="mt-2 text-sm text-danger" role="alert">
                                Не удалось загрузить список стадий.
                            </p>
                        )}
                    </div>

                    <div>
                        <h3 className="mb-2 text-sm font-semibold text-muted">Срок</h3>
                        <input
                            type="date"
                            value={task.due_date ?? ""}
                            onChange={(event) =>
                                updateMutation.mutate({ due_date: event.target.value || null })
                            }
                            className="w-full rounded border border-border bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        />
                    </div>
                </section>

                <div className="flex flex-col gap-4 md:flex-row md:items-start">
                    <nav
                        aria-label="Разделы задачи"
                        className="flex shrink-0 gap-1 overflow-x-auto pb-1 md:w-40 md:flex-col md:overflow-visible md:pb-0"
                    >
                        {navItems.map((item) => (
                            <button
                                key={item.key}
                                type="button"
                                onClick={() => setActiveSection(item.key)}
                                aria-current={activeSection === item.key ? "true" : undefined}
                                className={cn(
                                    "flex shrink-0 items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                                    activeSection === item.key
                                        ? "bg-surface-active text-foreground shadow-[var(--shadow-card)]"
                                        : "text-muted hover:bg-white/5 hover:text-foreground",
                                )}
                            >
                                <span>{item.label}</span>
                                {item.count !== null && (
                                    <span className="font-mono text-xs opacity-70">{item.count}</span>
                                )}
                            </button>
                        ))}
                    </nav>

                    <div className="min-w-0 flex-1">
                    {activeSection === "description" && (
                <section className="rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
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
                    )}

                    {activeSection === "files" && (
                <section
                    ref={attachmentSectionRef}
                    className="rounded-xl border border-white/[0.05] bg-surface-elevated p-4"
                >
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-sm font-semibold text-muted">
                            Файлы
                            {attachmentsQuery.data && (
                                <span className="ml-1.5 font-mono text-xs text-accent-secondary">
                                    · {attachmentsQuery.data.length}
                                </span>
                            )}
                        </h3>
                        <FileUploadControl
                            onFiles={async (files) => {
                                await uploadAttachmentMutation.mutateAsync(files);
                            }}
                            onError={setAttachmentError}
                            currentCount={attachmentsQuery.data?.length ?? 0}
                            disabled={attachmentsQuery.isPending || deleteAttachmentMutation.isPending}
                            uploading={uploadAttachmentMutation.isPending}
                            scopeRef={attachmentSectionRef}
                        />
                    </div>

                    {attachmentsQuery.isPending && <AttachmentsSkeleton />}
                    {attachmentsQuery.isError && (
                        <ErrorMessage message={(attachmentsQuery.error as Error).message} />
                    )}
                    {attachmentFiles.length > 0 ? (
                        <FileList
                            files={attachmentFiles}
                            removeDisabled={deleteAttachmentMutation.isPending}
                            onRemove={(file) => {
                                if (window.confirm(`Удалить файл «${file.name}»?`)) {
                                    deleteAttachmentMutation.mutate(Number(file.key));
                                }
                            }}
                        />
                    ) : !attachmentsQuery.isPending && !attachmentsQuery.isError ? (
                        <p className="text-sm text-muted">
                            Файлов пока нет. Выберите, перетащите или вставьте файл из буфера.
                        </p>
                    ) : null}

                    <p className="mt-2 text-[11px] text-muted">
                        До 20 файлов по 10 МБ · изображения, PDF, Office, текст и архивы
                    </p>
                    {attachmentError && (
                        <p className="mt-2 text-sm text-danger" role="alert" aria-live="polite">
                            {attachmentError}
                        </p>
                    )}
                </section>
                    )}

                    {activeSection === "documents" && (
                <section className="rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
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
                    )}

                    {activeSection === "comments" && (
                <section className="rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
                    <h3 className="mb-2 text-sm font-semibold text-muted">Комментарии</h3>
                    {commentsQuery.isPending && <CommentsSkeleton />}
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
                    )}

                    {activeSection === "history" && (
                <section className="rounded-xl border border-white/[0.05] bg-surface-elevated p-4">
                    <h3 className="mb-2 text-sm font-semibold text-muted">История</h3>
                    {activityQuery.isPending && <HistorySkeleton />}
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
                    )}
                    </div>
                </div>
        </Modal>
    );
}
