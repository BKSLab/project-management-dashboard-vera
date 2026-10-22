import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderInput, Link2, MessageSquare, Pencil, Trash2 } from "lucide-react";
import { api, apiUrl, endpoints, queryKeys } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDateTime, formatRelative, toDateInputValue } from "@/lib/dates";
import type { FileDescriptor } from "@/lib/files";
import type {
    DocumentListItem,
    LinkedDocument,
    ProjectMember,
    ProjectStage,
    Task,
    TaskActivity,
    TaskAttachment,
    TaskComment,
    TaskPriority,
    TaskStatus,
    WbsStructure,
} from "@/lib/types";
import { fullName, PRIORITY_LABELS, PRIORITY_ORDER } from "@/lib/types";
import { useUiStore } from "@/stores/ui";
import { useRenderedMarkdown } from "@/lib/useRenderedMarkdown";
import { Button, IconButton } from "@/components/ui/Button";
import { Drawer, DrawerSection } from "@/components/ui/Drawer";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { PriorityBadge, StatusDot } from "@/components/ui/Badge";
import { DueDate } from "@/components/ui/DueDate";
import { ErrorMessage, Skeleton } from "@/components/ui/States";
import { FileList } from "@/components/files/FileList";
import { FileUploadControl } from "@/components/files/FileUploadControl";
import { observerUserIds, participantUserId } from "@/lib/taskParticipants";
import { useCurrentUser } from "@/lib/useAuth";
import { TaskPeopleFields } from "@/components/tasks/TaskPeopleFields";
import { TaskRiskSection } from "@/components/risks/TaskRiskSection";
import { TaskChecklistSection } from "@/components/tasks/TaskChecklistSection";
import { TaskReportSection } from "@/components/tasks/TaskReportSection";
import { TaskTitleEditor } from "@/components/tasks/TaskTitleEditor";
import { MoveTaskDialog } from "@/components/tasks/MoveTaskDialog";
import { LocalUserSelect } from "@/components/tasks/LocalUserSelect";
import { isClosedStatus, TASK_STATUS_LABELS, TASK_STATUS_ORDER, taskKind } from "@/lib/tasks";
import { moveDeniedHint } from "@/lib/taskMove";
import { useTaskViewed } from "@/lib/useTaskViewed";
import type { TaskViewToken } from "@/lib/taskAttention";

const EVENT_LABELS: Record<TaskActivity["event_type"], string> = {
    STAGE_CHANGED: "Стадия",
    DUE_DATE_CHANGED: "Срок",
    START_DATE_CHANGED: "Начало",
    BASELINE_CHANGED: "Baseline",
    DESCRIPTION_CHANGED: "Описание изменено",
    PRIORITY_CHANGED: "Приоритет",
    ASSIGNEE_CHANGED: "Исполнитель",
    WBS_NODE_CHANGED: "Раздел ИСР",
    COMMENT_ADDED: "Добавлен комментарий",
    CHECKLIST_CHANGED: "Чек-лист изменён",
    TASK_MOVED: "Перенесена",
    LINKS_REMOVED: "При переносе снято",
};

function MarkdownBlock({ markdown }: { markdown: string }) {
    const html = useRenderedMarkdown(markdown);
    return (
        <div
            className="markdown-body text-[13px]"
            // Содержимое проходит через DOMPurify в renderMarkdown.
            dangerouslySetInnerHTML={{ __html: html }}
        />
    );
}

/**
 * Единая карточка задачи для канбана, списка и структуры: одна сущность
 * не должна иметь разных представлений на разных экранах (раздел 12).
 */
export function TaskDrawer() {
    const taskId = useUiStore((state) => state.selectedTaskId);
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);

    if (taskId === null) {
        return null;
    }
    // key сбрасывает черновики и локальные ошибки при переходе к другой задаче.
    return (
        <TaskDrawerContent
            key={taskId}
            taskId={taskId}
            onClose={() => setSelectedTaskId(null)}
        />
    );
}

function TaskDrawerContent({ taskId, onClose }: { taskId: number; onClose: () => void }) {
    const queryClient = useQueryClient();
    const filesSectionRef = useRef<HTMLDivElement>(null);
    const [isEditingDescription, setIsEditingDescription] = useState(false);
    const [descriptionDraft, setDescriptionDraft] = useState("");
    const [commentDraft, setCommentDraft] = useState("");
    const visibleCardRef = useRef<HTMLDivElement>(null);
    const reportSectionRef = useRef<HTMLDivElement>(null);
    const [reportComment, setReportComment] = useState<TaskComment | null>(null);
    const [moveDialogOpen, setMoveDialogOpen] = useState(false);
    const [editingComment, setEditingComment] = useState<TaskComment | null>(null);
    const [commentEditDraft, setCommentEditDraft] = useState("");
    const [documentToLink, setDocumentToLink] = useState("");
    const [attachmentError, setAttachmentError] = useState<string | null>(null);
    const currentUserQuery = useCurrentUser();

    const taskQuery = useQuery({
        queryKey: queryKeys.task(taskId),
        queryFn: async () => {
            const attention_view = await api.get<TaskViewToken>(`/api/v1/tasks/${taskId}/attention`);
            return { ...await api.get<Task>(endpoints.task(taskId)), attention_view };
        },
    });
    const task = taskQuery.data;
    const projectId = task?.project_id ?? undefined;
    const kind = task ? taskKind(task) : "PROJECT";
    const personal = kind === "PERSONAL";

    const stagesQuery = useQuery({
        queryKey: queryKeys.stages(projectId ?? 0),
        queryFn: () => api.get<ProjectStage[]>(endpoints.projectStages(projectId as number)),
        enabled: projectId !== undefined,
    });
    const membersQuery = useQuery({
        queryKey: queryKeys.projectMembers(projectId ?? 0),
        queryFn: () => api.get<ProjectMember[]>(endpoints.projectMembers(projectId as number)),
        enabled: projectId !== undefined,
    });
    const commentsQuery = useQuery({
        queryKey: queryKeys.taskComments(taskId),
        queryFn: () => api.get<TaskComment[]>(endpoints.taskComments(taskId)),
    });
    const activityQuery = useQuery({
        queryKey: queryKeys.taskActivity(taskId),
        queryFn: () => api.get<TaskActivity[]>(endpoints.taskActivity(taskId)),
    });
    const attachmentsQuery = useQuery({
        queryKey: queryKeys.taskAttachments(taskId),
        queryFn: () => api.get<TaskAttachment[]>(endpoints.taskAttachments(taskId)),
    });
    const linksQuery = useQuery({
        queryKey: queryKeys.taskLinks(taskId),
        queryFn: () => api.get<LinkedDocument[]>(endpoints.taskLinks(taskId)),
        enabled: projectId !== undefined,
    });
    const documentsQuery = useQuery({
        queryKey: queryKeys.documents(projectId ?? 0),
        queryFn: () => api.get<DocumentListItem[]>(endpoints.projectDocuments(projectId as number)),
        enabled: projectId !== undefined,
    });
    const wbsQuery = useQuery({
        queryKey: queryKeys.wbs(projectId ?? 0),
        queryFn: () => api.get<WbsStructure>(endpoints.wbs(projectId as number)),
        enabled: projectId !== undefined && task?.wbs_node_id !== null,
    });

    useTaskViewed(taskId, commentsQuery.isSuccess && !commentsQuery.isFetching && attachmentsQuery.isSuccess && !attachmentsQuery.isFetching && activityQuery.isSuccess && !activityQuery.isFetching ? task?.attention_view : undefined, visibleCardRef);

    /** После любого изменения задачи обновляем все её представления. */
    const invalidateTask = () => {
        queryClient.invalidateQueries({ queryKey: queryKeys.task(taskId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.taskActivity(taskId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
        queryClient.invalidateQueries({ queryKey: queryKeys.myTasks });
        if (projectId !== undefined) {
            queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
        }
    };

    const updateMutation = useMutation({
        mutationFn: (data: Record<string, unknown>) =>
            api.patch<Task>(endpoints.task(taskId), data),
        onSuccess: (updated) => {
            queryClient.setQueryData(queryKeys.task(taskId), updated);
            setIsEditingDescription(false);
            invalidateTask();
        },
    });

    const moveMutation = useMutation({
        mutationFn: (stageId: number) =>
            api.patch<Task>(endpoints.taskMove(taskId), { stage_id: stageId }),
        onSuccess: invalidateTask,
    });

    const commentMutation = useMutation({
        mutationFn: () =>
            api.post<TaskComment>(endpoints.taskComments(taskId), {
                body_md: commentDraft,
            }),
        onSuccess: () => {
            setCommentDraft("");
            queryClient.invalidateQueries({ queryKey: queryKeys.taskComments(taskId) });
            invalidateTask();
        },
    });

    const statusMutation = useMutation({
        mutationFn: (status: TaskStatus) => api.patch<Task>(endpoints.taskStatus(taskId), { status }),
        onSuccess: invalidateTask,
    });
    const editCommentMutation = useMutation({
        mutationFn: () => api.patch<TaskComment>(`/api/v1/comments/${editingComment!.id}`, { body_md: commentEditDraft, expected_body_md: editingComment!.body_md }),
        onSuccess: () => { setEditingComment(null); queryClient.invalidateQueries({ queryKey: queryKeys.taskComments(taskId) }); invalidateTask(); },
    });
    const deleteCommentMutation = useMutation({
        mutationFn: (id: number) => api.delete(`/api/v1/comments/${id}`),
        onSuccess: () => { queryClient.invalidateQueries({ queryKey: queryKeys.taskComments(taskId) }); invalidateTask(); },
    });

    const linkMutation = useMutation({
        mutationFn: (documentId: number) =>
            api.post(endpoints.links(), { document_id: documentId, task_id: taskId }),
        onSuccess: () => {
            setDocumentToLink("");
            queryClient.invalidateQueries({ queryKey: queryKeys.taskLinks(taskId) });
        },
    });

    const unlinkMutation = useMutation({
        mutationFn: (linkId: number) => api.delete(endpoints.link(linkId)),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.taskLinks(taskId) });
        },
    });

    const uploadMutation = useMutation({
        mutationFn: async (files: File[]) => {
            for (const file of files) {
                const body = new FormData();
                body.append("file", file);
                await api.postForm<TaskAttachment>(endpoints.taskAttachments(taskId), body);
            }
        },
        onMutate: () => setAttachmentError(null),
        onError: (error) => setAttachmentError((error as Error).message),
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.taskAttachments(taskId) });
        },
    });

    const deleteAttachmentMutation = useMutation({
        mutationFn: (attachmentId: number) =>
            api.delete(endpoints.taskAttachment(taskId, attachmentId)),
        onMutate: () => setAttachmentError(null),
        onError: (error) => setAttachmentError((error as Error).message),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.taskAttachments(taskId) });
        },
    });

    const attachmentFiles = useMemo<FileDescriptor[]>(
        () =>
            (attachmentsQuery.data ?? []).map((attachment) => ({
                key: String(attachment.id),
                name: attachment.original_name,
                url: apiUrl(attachment.content_url),
                size: attachment.size,
                mime: attachment.content_type,
                previewable: attachment.previewable,
            })),
        [attachmentsQuery.data],
    );

    const unlinkedDocuments = useMemo(() => {
        const linkedIds = new Set((linksQuery.data ?? []).map((link) => link.document_id));
        return (documentsQuery.data ?? []).filter((document) => !linkedIds.has(document.id));
    }, [documentsQuery.data, linksQuery.data]);

    const stage = stagesQuery.data?.find((item) => item.id === task?.stage_id);
    const wbsNode = wbsQuery.data?.nodes.find((node) => node.id === task?.wbs_node_id);
    const canChangeReporter = personal ? participantUserId(task!, "REPORTER") === currentUserQuery.data?.id : membersQuery.data?.some(
        (member) =>
            member.user.id === currentUserQuery.data?.id && member.role === "OWNER",
    );
    const mutationError =
        statusMutation.error ?? editCommentMutation.error ?? deleteCommentMutation.error ??
        updateMutation.error ??
        moveMutation.error ??
        commentMutation.error ??
        linkMutation.error ??
        unlinkMutation.error;

    const header = task ? (
        <div className="flex min-w-0 flex-col gap-1.5">
            <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] text-muted">{task.key}</span>
                <PriorityBadge priority={task.priority} showLow />
            </div>
            <TaskTitleEditor title={task.title} canEdit saving={updateMutation.isPending} error={updateMutation.error?.message}
                onSave={async title => { try { await updateMutation.mutateAsync({ title }); return true; } catch { return false; } }} />
            <Button size="sm" variant="ghost" icon={<FolderInput size={13} />} disabled={Boolean(moveDeniedHint(kind, true, participantUserId(task, "REPORTER") === currentUserQuery.data?.id))}
                title={moveDeniedHint(kind, true, participantUserId(task, "REPORTER") === currentUserQuery.data?.id)} onClick={() => setMoveDialogOpen(true)}>Переместить…</Button>
        </div>
    ) : (
        <Skeleton className="h-9 w-56" />
    );

    return (
        <Drawer
            label={task ? `Задача ${task.key}` : "Задача"}
            isOpen
            onClose={onClose}
            header={header}
        >
            {taskQuery.isPending && (
                <div className="flex flex-col gap-3 p-4">
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-32 w-full" />
                </div>
            )}
            {taskQuery.error && (
                <div className="p-4">
                    <ErrorMessage message={(taskQuery.error as Error).message} />
                </div>
            )}

            {task && (
                <div ref={visibleCardRef}>
                    {mutationError && (
                        <div className="px-4 pt-4">
                            <ErrorMessage message={(mutationError as Error).message} />
                        </div>
                    )}

                    <DrawerSection title="Свойства">
                        <div className="grid gap-3 sm:grid-cols-2">
                            {personal ? <Field label="Статус">{id => <Select id={id} value={task.status ?? "NEW"} disabled={statusMutation.isPending} onChange={event => statusMutation.mutate(event.target.value as TaskStatus)}>{TASK_STATUS_ORDER.map(status => <option key={status} value={status}>{TASK_STATUS_LABELS[status]}</option>)}</Select>}</Field> : <Field label="Стадия">
                                {(id) => (
                                    <Select
                                        id={id}
                                        value={task.stage_id ?? ""}
                                        disabled={stagesQuery.isPending || moveMutation.isPending}
                                        onChange={(event) =>
                                            moveMutation.mutate(Number(event.target.value))
                                        }
                                    >
                                        {stagesQuery.data?.map((item) => (
                                            <option key={item.id} value={item.id}>
                                                {item.name}
                                            </option>
                                        ))}
                                    </Select>
                                )}
                            </Field>}

                            <Field label="Приоритет">
                                {(id) => (
                                    <Select
                                        id={id}
                                        value={task.priority}
                                        disabled={updateMutation.isPending}
                                        onChange={(event) =>
                                            updateMutation.mutate({
                                                priority: event.target.value as TaskPriority,
                                            })
                                        }
                                    >
                                        {PRIORITY_ORDER.map((priority) => (
                                            <option key={priority} value={priority}>
                                                {PRIORITY_LABELS[priority]}
                                            </option>
                                        ))}
                                    </Select>
                                )}
                            </Field>

                            <Field label="Начало">
                                {(id) => (
                                    <Input
                                        id={id}
                                        type="date"
                                        value={toDateInputValue(task.start_date)}
                                        max={task.due_date ?? undefined}
                                        onChange={(event) =>
                                            updateMutation.mutate({
                                                start_date: event.target.value || null,
                                            })
                                        }
                                    />
                                )}
                            </Field>

                            <Field label="Завершение">
                                {(id) => (
                                    <Input
                                        id={id}
                                        type="date"
                                        value={toDateInputValue(task.due_date)}
                                        min={task.start_date ?? undefined}
                                        onChange={(event) =>
                                            updateMutation.mutate({
                                                due_date: event.target.value || null,
                                            })
                                        }
                                    />
                                )}
                            </Field>

                            <div className="border-t border-line-subtle pt-3 sm:col-span-2">
                                {personal ? <div className="grid gap-3 sm:grid-cols-2">
                                    <Field label="Исполнитель">{() => <LocalUserSelect label="Исполнитель" selected={(task.participants ?? []).filter(item => item.role === "EXECUTOR").map(item => item.user)} disabled={updateMutation.isPending} onChange={users => updateMutation.mutate({ executor_id: users[0]?.id ?? null })} />}</Field>
                                    <Field label="Постановщик">{() => <LocalUserSelect label="Постановщик" selected={(task.participants ?? []).filter(item => item.role === "REPORTER").map(item => item.user)} disabled={!canChangeReporter || updateMutation.isPending} onChange={users => updateMutation.mutate({ reporter_id: users[0]?.id ?? null })} />}</Field>
                                    <div className="sm:col-span-2"><Field label="Наблюдатели">{() => <LocalUserSelect label="Наблюдатели" multiple selected={(task.participants ?? []).filter(item => item.role === "OBSERVER").map(item => item.user)} disabled={updateMutation.isPending} onChange={users => updateMutation.mutate({ observer_ids: users.map(user => user.id) })} />}</Field></div>
                                </div> : <TaskPeopleFields
                                    members={membersQuery.data ?? []}
                                    executorId={participantUserId(task, "EXECUTOR")}
                                    reporterId={participantUserId(task, "REPORTER")}
                                    observerIds={observerUserIds(task)}
                                    canChangeReporter={canChangeReporter}
                                    legacyExecutorLabel={task.assignee}
                                    disabled={
                                        membersQuery.isPending || updateMutation.isPending
                                    }
                                    onExecutorChange={(userId) =>
                                        updateMutation.mutate({ executor_id: userId })
                                    }
                                    onReporterChange={(userId) =>
                                        updateMutation.mutate({ reporter_id: userId })
                                    }
                                    onObserversChange={(userIds) =>
                                        updateMutation.mutate({ observer_ids: userIds })
                                    }
                                />
                                }
                                {membersQuery.error && (
                                    <p className="mt-2 text-[11px] text-danger">
                                        Не удалось загрузить команду проекта.
                                    </p>
                                )}
                            </div>

                            {!personal && <div className="flex flex-col gap-1.5">
                                <span className="text-xs font-medium text-secondary">Раздел ИСР</span>
                                <p className="flex h-8 items-center text-[13px] text-muted">
                                    {wbsNode ? wbsNode.title : "Не распределена"}
                                </p>
                            </div>}
                        </div>

                        <div className="mt-3 flex items-center gap-3 text-[11px] text-muted">
                            {stage && (
                                <span className="inline-flex items-center gap-1.5">
                                    <StatusDot color={stage.color} />
                                    {stage.name}
                                </span>
                            )}
                            <DueDate value={task.due_date} isDone={personal ? isClosedStatus(task.status) : stage?.is_done_stage} />
                        </div>
                    </DrawerSection>

                    <DrawerSection
                        title="Описание"
                        action={
                            !isEditingDescription && (
                                <IconButton
                                    label="Редактировать описание"
                                    size="sm"
                                    onClick={() => {
                                        setDescriptionDraft(task.description_md ?? "");
                                        setIsEditingDescription(true);
                                    }}
                                >
                                    <Pencil size={13} aria-hidden="true" />
                                </IconButton>
                            )
                        }
                    >
                        {isEditingDescription ? (
                            <div className="flex flex-col gap-2">
                                <Textarea
                                    rows={8}
                                    value={descriptionDraft}
                                    aria-label="Описание задачи в Markdown"
                                    onChange={(event) => setDescriptionDraft(event.target.value)}
                                />
                                <div className="flex justify-end gap-2">
                                    <Button
                                        size="sm"
                                        onClick={() => setIsEditingDescription(false)}
                                    >
                                        Отмена
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="primary"
                                        disabled={updateMutation.isPending}
                                        onClick={() =>
                                            updateMutation.mutate({
                                                description_md: descriptionDraft || null,
                                            })
                                        }
                                    >
                                        Сохранить
                                    </Button>
                                </div>
                            </div>
                        ) : task.description_md ? (
                            <MarkdownBlock markdown={task.description_md} />
                        ) : (
                            <p className="text-[13px] text-muted">
                                Описания пока нет. Добавьте контекст, чтобы задача была понятна.
                            </p>
                        )}
                    </DrawerSection>

                    {projectId !== undefined && <TaskRiskSection projectId={projectId} projectKey={task.key.slice(0, task.key.lastIndexOf("-"))} taskId={task.id} />}
                    <TaskChecklistSection task={task} description={isEditingDescription ? descriptionDraft : task.description_md ?? ""} />
                    {projectId !== undefined && <DrawerSection title="Документы" count={linksQuery.data?.length ?? null}>
                        <div className="flex flex-col gap-2">
                            {linksQuery.data?.map((link) => (
                                <div
                                    key={link.link_id}
                                    className="flex items-center gap-2 rounded-[var(--radius-control)] bg-white/[0.03] px-2.5 py-1.5"
                                >
                                    <Link2 size={13} className="shrink-0 text-muted" aria-hidden="true" />
                                    <span className="min-w-0 flex-1 truncate text-[13px] text-secondary">
                                        {link.title}
                                    </span>
                                    <IconButton
                                        label={`Отвязать документ ${link.title}`}
                                        size="sm"
                                        disabled={unlinkMutation.isPending}
                                        onClick={() => unlinkMutation.mutate(link.link_id)}
                                    >
                                        <Trash2 size={12} aria-hidden="true" />
                                    </IconButton>
                                </div>
                            ))}
                            {unlinkedDocuments.length > 0 && (
                                <div className="flex gap-2">
                                    <Select
                                        aria-label="Документ для связи с задачей"
                                        value={documentToLink}
                                        onChange={(event) => setDocumentToLink(event.target.value)}
                                    >
                                        <option value="">Связать документ…</option>
                                        {unlinkedDocuments.map((document) => (
                                            <option key={document.id} value={document.id}>
                                                {document.title}
                                            </option>
                                        ))}
                                    </Select>
                                    <Button
                                        size="sm"
                                        disabled={documentToLink === "" || linkMutation.isPending}
                                        onClick={() => linkMutation.mutate(Number(documentToLink))}
                                    >
                                        Связать
                                    </Button>
                                </div>
                            )}
                            {linksQuery.data?.length === 0 && unlinkedDocuments.length === 0 && (
                                <p className="text-[13px] text-muted">
                                    В проекте пока нет документов для связи.
                                </p>
                            )}
                        </div>
                    </DrawerSection>}

                    <DrawerSection title="Файлы" count={attachmentsQuery.data?.length ?? null}>
                        <div ref={filesSectionRef} className="flex flex-col gap-2.5">
                            {attachmentError && <ErrorMessage message={attachmentError} />}
                            <FileList
                                files={attachmentFiles}
                                onRemove={(file) =>
                                    deleteAttachmentMutation.mutate(Number(file.key))
                                }
                                removeDisabled={deleteAttachmentMutation.isPending}
                            />
                            <FileUploadControl
                                onFiles={(files) => uploadMutation.mutate(files)}
                                onError={setAttachmentError}
                                currentCount={attachmentFiles.length}
                                uploading={uploadMutation.isPending}
                                scopeRef={filesSectionRef}
                            />
                        </div>
                    </DrawerSection>

                    <DrawerSection title="Комментарии" count={commentsQuery.data?.length ?? null}>
                        <div className="flex flex-col gap-2.5">
                            {commentsQuery.data?.map((comment) => (
                                <article
                                    key={comment.id}
                                    className="rounded-md border-l-2 border-accent-border bg-white/[0.025] px-2.5 py-2"
                                >
                                    <div className="mb-1 flex items-center gap-2 text-[11px] text-muted">
                                        <MessageSquare size={11} aria-hidden="true" />
                                        <span className="font-medium text-secondary">
                                            {comment.author ? fullName(comment.author) : comment.author_name ?? "Без подписи"}
                                        </span>
                                        <time dateTime={comment.created_at}>
                                            {formatRelative(comment.created_at)}
                                        </time>
                                    </div>
                                    {editingComment?.id === comment.id ? <div className="flex flex-col gap-2"><Textarea aria-label="Изменить комментарий" value={commentEditDraft} onChange={event => setCommentEditDraft(event.target.value)} /><div className="flex gap-2"><Button size="sm" disabled={!commentEditDraft.trim() || editCommentMutation.isPending} onClick={() => editCommentMutation.mutate()}>Сохранить</Button><Button size="sm" variant="ghost" onClick={() => setEditingComment(null)}>Отмена</Button></div></div> : <p className="text-[13px] break-words whitespace-pre-wrap text-secondary">{comment.body_md}</p>}
                                    <div className="mt-2 flex gap-2">
                                        {(!comment.author || comment.author.id === currentUserQuery.data?.id) && <>
                                            <Button size="sm" variant="ghost" onClick={() => { setEditingComment(comment); setCommentEditDraft(comment.body_md); }}>Изменить</Button>
                                            <Button size="sm" variant="ghost" disabled={deleteCommentMutation.isPending} onClick={() => deleteCommentMutation.mutate(comment.id)}>Удалить</Button>
                                        </>}
                                        <Button size="sm" variant="ghost" onClick={() => { setReportComment(comment); reportSectionRef.current?.scrollIntoView({ behavior: "smooth" }); }}>Считать отчётом</Button>
                                    </div>
                                </article>
                            ))}
                            {commentsQuery.data?.length === 0 && (
                                <p className="text-[13px] text-muted">Комментариев пока нет.</p>
                            )}

                            <div className="flex flex-col gap-2 pt-1">
                                <Textarea
                                    rows={3}
                                    value={commentDraft}
                                    aria-label="Текст комментария"
                                    placeholder="Написать комментарий…"
                                    onChange={(event) => setCommentDraft(event.target.value)}
                                />
                                <div className="flex justify-end">
                                    <Button
                                        size="sm"
                                        variant="primary"
                                        disabled={
                                            commentDraft.trim() === "" || commentMutation.isPending
                                        }
                                        onClick={() => commentMutation.mutate()}
                                    >
                                        Отправить
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </DrawerSection>

                    <div ref={reportSectionRef}><DrawerSection title="Итоговый отчёт"><TaskReportSection taskId={taskId} active selectedComment={reportComment} clearComment={() => setReportComment(null)} /></DrawerSection></div>

                    <DrawerSection title="История" count={activityQuery.data?.length ?? null}>
                        <ol className="flex flex-col gap-2">
                            {activityQuery.data?.map((event) => (
                                <li key={event.id} className="flex gap-2.5 text-[12px]">
                                    <span
                                        aria-hidden="true"
                                        className="mt-1.5 size-1.5 shrink-0 rounded-full bg-line-strong"
                                    />
                                    <div className="min-w-0 flex-1">
                                        <p className="text-secondary">
                                            <span className="text-muted">
                                                {EVENT_LABELS[event.event_type]}
                                            </span>
                                            {event.from_value && event.to_value && (
                                                <span className="ml-1">
                                                    <span className="text-disabled line-through">
                                                        {event.from_value}
                                                    </span>
                                                    <span className="mx-1 text-disabled">→</span>
                                                    <span>{event.to_value}</span>
                                                </span>
                                            )}
                                            {!event.from_value && event.to_value && (
                                                <span className="ml-1">{event.to_value}</span>
                                            )}
                                        </p>
                                        {event.actor_name && <p className="text-[11px] text-muted">{event.actor_name}{event.via_api_key_label ? ` · через ${event.via_api_key_label}` : ""}</p>}
                                        <time
                                            dateTime={event.created_at}
                                            className={cn("text-[11px] text-disabled")}
                                        >
                                            {formatDateTime(event.created_at)}
                                        </time>
                                    </div>
                                </li>
                            ))}
                            {activityQuery.data?.length === 0 && (
                                <li className="text-[13px] text-muted">Изменений пока не было.</li>
                            )}
                        </ol>
                    </DrawerSection>
                    {moveDialogOpen && <MoveTaskDialog task={task} kind={kind} onClose={() => setMoveDialogOpen(false)} onMoved={() => { invalidateTask(); if (projectId) queryClient.invalidateQueries({ queryKey: queryKeys.wbs(projectId) }); }} />}
                </div>
            )}
        </Drawer>
    );
}
