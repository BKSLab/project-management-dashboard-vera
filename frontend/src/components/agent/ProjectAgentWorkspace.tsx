import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
    Bot,
    Database,
    Paperclip,
    Plus,
    RefreshCw,
    Send,
    Sparkles,
} from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type {
    Project,
    KnowledgeStatus,
    KnowledgeEntityType,
} from "@/lib/types";
import { useCurrentUser } from "@/lib/useAuth";
import { useAgentChatStore } from "@/stores/agentChat";
import { useAgentConversations } from "@/lib/useAgentConversations";
import { useRenderedMarkdown } from "@/lib/useRenderedMarkdown";
import { AgentEntityCard } from "@/components/agent/AgentEntityCard";
import { actionSources } from "@/lib/agentCards";
import { Button } from "@/components/ui/Button";
import { AgentActionCard } from "@/components/projects/AgentActionCard";
import { ErrorMessage } from "@/components/ui/States";
import { cn } from "@/lib/cn";

const STARTERS = [
    "Дай краткую сводку проекта и текущие риски",
    "Какие задачи просрочены и кто за них отвечает?",
    "Что уже сделано, а что сейчас в работе?",
    "Какие решения и требования зафиксированы в документах?",
];

const SOURCE_LABELS: Record<KnowledgeEntityType, string> = {
    project: "Паспорт", task: "Задачи и чек-листы", document: "Документы", comment: "Комментарии",
    attachment: "Файлы", milestone: "Вехи", risk: "Риски", wbs_node: "Разделы ИСР",
    stage: "Стадии", sticker: "Стикеры", member: "Команда", activity: "История задач",
    deadline_change: "История сроков", analytics_report: "Сохранённые отчёты",
};

function MarkdownAnswer({ content }: { content: string }) {
    const html = useRenderedMarkdown(content);
    return (
        <div
            className="markdown-body text-[13px]"
            // HTML очищается DOMPurify внутри общего Markdown-renderer.
            dangerouslySetInnerHTML={{ __html: html }}
        />
    );
}

export function ProjectAgentWorkspace({ project, compact = false }: { project: Project; compact?: boolean }) {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const endRef = useRef<HTMLDivElement>(null);
    const [searchParams, setSearchParams] = useSearchParams();
    const userId = useCurrentUser().data?.id ?? 0;
    const sessionKey = `${userId}:${project.id}`;
    const rememberedId = useAgentChatStore((state) => state.conversations[sessionKey]);
    const select = useAgentChatStore((state) => state.select);
    const updateDraft = useAgentChatStore((state) => state.updateDraft);
    const clearDraft = useAgentChatStore((state) => state.clearDraft);
    const requestedId = compact ? 0 : Number(searchParams.get("conversation"));
    const conversationId = Number.isSafeInteger(requestedId) && requestedId > 0 ? requestedId : rememberedId ?? null;
    const mounted = useRef(true);
    useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
    useEffect(() => {
        if (conversationId != null && conversationId !== rememberedId) select(sessionKey, conversationId);
    }, [conversationId, rememberedId, select, sessionKey]);
    const chat = useAgentConversations(project.id, conversationId);
    const conversations = chat.conversations.data?.pages.flatMap((page) => page.items) ?? [];
    const messages = chat.messages.data?.pages.slice().reverse().flatMap((page) => page.items) ?? [];
    const fileInputRef = useRef<HTMLInputElement>(null);
    const draftKey = `${sessionKey}:${conversationId ?? "new"}`;
    const draft = useAgentChatStore((state) => state.drafts[draftKey]);
    const question = draft?.content ?? "";
    const selectedFiles = draft?.files ?? [];
    const sendingRef = useRef(false);
    const busy = messages.some((message) => message.status === "queued" || message.status === "processing");
    const sending = chat.mutating;
    const loading = chat.conversations.isPending || (conversationId != null && chat.messages.isPending);
    const chatError = chat.conversations.error || chat.messages.error || chat.create.error || chat.send.error || chat.retry.error || chat.decide.error || chat.upload.error || chat.removeUpload.error;
    const lastMessage = messages.at(-1);

    function selectConversation(id: number) {
        select(sessionKey, id);
        if (!compact && mounted.current) setSearchParams((previous) => { const next = new URLSearchParams(previous); next.set("conversation", String(id)); return next; });
        chat.send.reset();
        chat.retry.reset();
        chat.decide.reset();
        chat.upload.reset();
        chat.removeUpload.reset();
    }

    const firstConversationId = conversations[0]?.id;
    const completedActions = messages.flatMap((message) => message.actions ?? []).filter((action) => action.status === "completed").map((action) => action.id).join(",");
    useEffect(() => {
        if (!completedActions) return;
        let active = true;
        async function refreshProject() {
            try {
                const current = await api.get<Project>(endpoints.project(project.id));
                if (!active) return;
                if (current.key !== project.key) {
                    queryClient.setQueryData<Project[]>(queryKeys.projects, (previous) => previous?.map((item) => item.id === current.id ? current : item));
                    const prefix = `/projects/${project.key}`;
                    if (window.location.pathname === prefix || window.location.pathname.startsWith(`${prefix}/`)) {
                        navigate(`${window.location.pathname.replace(prefix, `/projects/${current.key}`)}${window.location.search}`, { replace: true });
                    }
                }
            } finally {
                if (active) void queryClient.invalidateQueries({ predicate: (query) => {
                    const [kind, id, section] = query.queryKey;
                    return (kind === "projects" && (id == null || id === project.id) && section !== "agent")
                        || kind === "tasks" || kind === "documents" || kind === "dashboard";
                } });
            }
        }
        void refreshProject().catch(() => { /* Общие запросы покажут актуальное состояние доступа. */ });
        return () => { active = false; };
    }, [completedActions, project.id, project.key, queryClient, navigate]);
    useEffect(() => {
        if (conversationId == null && firstConversationId != null) {
            select(sessionKey, firstConversationId);
            if (!compact) setSearchParams((previous) => { const next = new URLSearchParams(previous); next.set("conversation", String(firstConversationId)); return next; }, { replace: true });
        }
    }, [conversationId, firstConversationId, compact, select, sessionKey, setSearchParams]);

    const statusQuery = useQuery({
        enabled: !compact,
        queryKey: queryKeys.projectKnowledgeStatus(project.id),
        queryFn: () =>
            api.get<KnowledgeStatus>(endpoints.projectKnowledgeStatus(project.id)),
        refetchInterval: (query) => query.state.data?.ready ? 30000 : 10000,
    });

    const reindexMutation = useMutation({
        mutationFn: () =>
            api.post<{ queued: boolean }>(endpoints.projectKnowledgeReindex(project.id)),
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: queryKeys.projectKnowledgeStatus(project.id),
            });
        },
    });

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, [conversationId, lastMessage?.id, lastMessage?.status]);

    async function submit(value = question) {
        const normalized = value.trim();
        if (normalized.length < 2 || sending || sendingRef.current || busy || loading || chat.messages.isError) return;
        sendingRef.current = true;
        const requestId = draft?.content.trim() === normalized ? draft.requestId : crypto.randomUUID();
        updateDraft(draftKey, { content: normalized, files: selectedFiles, requestId });
        let id = conversationId;
        try {
            if (id == null) {
                id = (await chat.create.mutateAsync()).id;
                updateDraft(`${sessionKey}:${id}`, { content: normalized, files: selectedFiles, requestId });
                clearDraft(draftKey, requestId);
                selectConversation(id);
            }
            await chat.send.mutateAsync({ id, content: normalized, requestId, fileIds: selectedFiles.map((file) => file.id) });
            clearDraft(draftKey, requestId);
            clearDraft(`${sessionKey}:${id}`, requestId);
        } catch {
            // Черновик и UUID сохраняются для повтора в любом представлении чата.
        } finally {
            sendingRef.current = false;
        }
    }

    async function newConversation() {
        if (sending || sendingRef.current) return;
        sendingRef.current = true;
        try {
            selectConversation((await chat.create.mutateAsync()).id);
        } catch {
            // Состояние ошибки отображается рядом с редактором сообщения.
        } finally {
            sendingRef.current = false;
        }
    }

    async function uploadFiles(files: File[]) {
        if (sending || sendingRef.current || busy || loading) return;
        sendingRef.current = true;
        let id = conversationId;
        try {
            if (id == null) {
                id = (await chat.create.mutateAsync()).id;
                updateDraft(`${sessionKey}:${id}`, { content: question, files: selectedFiles });
                if (draft) clearDraft(draftKey, draft.requestId);
                selectConversation(id);
            }
            for (const file of files.slice(0, 5 - selectedFiles.length)) {
                const uploaded = await chat.upload.mutateAsync({ id, file });
                const key = `${sessionKey}:${id}`;
                updateDraft(key, { files: [...(useAgentChatStore.getState().drafts[key]?.files ?? []), uploaded] });
            }
        } catch { /* Уже загруженные файлы сохраняются, ошибка показывается в форме. */ }
        finally { sendingRef.current = false; }
    }

    async function removeFile(fileId: string) {
        if (conversationId == null || sending || busy) return;
        try {
            await chat.removeUpload.mutateAsync({ id: conversationId, fileId });
            updateDraft(draftKey, { files: (useAgentChatStore.getState().drafts[draftKey]?.files ?? []).filter((file) => file.id !== fileId) });
        } catch { /* Ошибка показывается в форме. */ }
    }

    function onSubmit(event: FormEvent) {
        event.preventDefault();
        void submit();
    }

    function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            void submit();
        }
    }

    const status = statusQuery.data;
    const indexing = Boolean(status && (status.pending_jobs > 0 || status.processing_jobs > 0));

    return (
        <div className="h-full min-h-0">
            <div className={cn("mx-auto grid h-full w-full", !compact && "max-w-6xl gap-4 p-5 lg:grid-cols-[minmax(0,1fr)_280px]")}>
                <section aria-label="Диалог с агентом" className={cn("ai-surface flex min-h-0 min-w-0 flex-col overflow-hidden", !compact && "rounded-[var(--radius-panel)] border border-ai-border shadow-card")}>
                    {!compact && <div className="flex items-center justify-between gap-3 border-b border-line-subtle px-4 py-3">
                        <div className="flex min-w-0 items-center gap-2.5">
                            <span className="ai-mark flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-control)] text-ai-blue">
                                <Bot size={17} aria-hidden="true" />
                            </span>
                            <div className="min-w-0">
                                <h2 className="text-[13px] font-semibold text-primary">Агент проекта</h2>
                                <p className="truncate text-[11px] text-muted">
                                    {project.name} · личные диалоги
                                </p>
                            </div>
                        </div>
                        <span
                            className={cn(
                                "rounded-[5px] border px-2 py-0.5 text-[10px] font-medium",
                                status?.ready
                                    ? "border-success/30 bg-success/10 text-success"
                                    : "border-warning/30 bg-warning/10 text-warning",
                            )}
                        >
                            {status?.ready ? "Вики готова" : indexing ? "Обновление знаний" : status?.enabled ? "Контекст неполный" : "Поиск по данным проекта"}
                        </span>
                    </div>}

                    <div className="flex flex-wrap items-center gap-2 border-b border-line-subtle px-4 py-2">
                        <select aria-label="Диалог" value={conversationId ?? ""}
                            disabled={sending || chat.conversations.isPending}
                            onChange={(event) => selectConversation(Number(event.target.value))}
                            className="min-w-0 flex-1 rounded-[var(--radius-control)] border border-line bg-surface px-2 py-1.5 text-[12px] text-primary">
                            {conversationId == null && <option value="">Начните первый разговор</option>}
                            {conversationId != null && !conversations.some((item) => item.id === conversationId) && <option value={conversationId}>Текущий диалог</option>}
                            {conversations.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                        </select>
                        <Button size="sm" icon={<Plus size={13} />} disabled={sending || loading} onClick={() => void newConversation()}>Новый диалог</Button>
                        {chat.conversations.hasNextPage && <Button size="sm" disabled={chat.conversations.isFetchingNextPage} onClick={() => void chat.conversations.fetchNextPage()}>Ещё диалоги</Button>}
                    </div>

                    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-4 py-5" aria-live="polite">
                        {loading ? <p className="text-[13px] text-muted">Загружаю переписку…</p> : messages.length === 0 ? (
                            <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center gap-5 py-8 text-center">
                                <span className="ai-mark flex size-11 items-center justify-center rounded-[var(--radius-card)] text-ai-blue">
                                    <Sparkles size={22} aria-hidden="true" />
                                </span>
                                <div className="flex flex-col gap-1.5">
                                    <h3 className="text-base font-semibold text-primary">
                                        Спросите что угодно о {project.name}
                                    </h3>
                                    <p className="text-[13px] text-muted">
                                        Агент сверяет семантическую базу с актуальным состоянием задач.
                                    </p>
                                </div>
                                <div className={cn("grid w-full border-y border-line-subtle", !compact && "sm:grid-cols-2")}>
                                    {STARTERS.map((starter) => (
                                        <button
                                            key={starter}
                                            type="button"
                                            disabled={sending || busy || Boolean(chatError)}
                                            onClick={() => void submit(starter)}
                                            className="px-3 py-2.5 text-left text-[12px] text-secondary transition-colors hover:bg-ai-soft hover:text-primary sm:odd:border-r sm:odd:border-line-subtle"
                                        >
                                            {starter}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="mx-auto flex max-w-3xl flex-col gap-4">
                                {chat.messages.hasNextPage && <Button size="sm" disabled={chat.messages.isFetchingNextPage} onClick={() => void chat.messages.fetchNextPage()}>Предыдущие сообщения</Button>}
                                {messages.map((message) => (
                                    <div
                                        key={message.id}
                                        className={cn(
                                            "flex",
                                            message.role === "user" ? "justify-end" : "justify-start",
                                        )}
                                    >
                                        <div
                                            className={cn(
                                                "min-w-0 rounded-lg px-3.5 py-3", compact ? "max-w-full" : "max-w-[88%]",
                                                message.role === "user"
                                                    ? "bg-accent/85 text-on-accent"
                                                    : "bg-ai-soft text-secondary shadow-card",
                                            )}
                                        >
                                            {message.status === "queued" || message.status === "processing" ? (
                                                <div className="flex items-center gap-2 text-[12px] text-muted"><RefreshCw size={13} className="animate-spin" />{message.status === "queued" ? "Вопрос сохранён. Ожидаю ответа…" : "Агент сверяет источники…"}</div>
                                            ) : message.status === "failed" ? (
                                                <div className="space-y-2 text-[12px]">
                                                    <p className="text-danger">{message.error}</p>
                                                    {message.id === lastMessage?.id && <Button size="sm" disabled={sending} onClick={() => chat.retry.mutate({ id: conversationId!, messageId: message.id })}>Повторить ответ</Button>}
                                                </div>
                                            ) : message.role === "assistant" ? (
                                                message.content.trim() ? <MarkdownAnswer content={message.content} /> : null
                                            ) : (
                                                <p className="whitespace-pre-wrap text-[13px] leading-relaxed">
                                                    {message.content}
                                                </p>
                                            )}
                                            {(message.files ?? []).map((file) => <p key={file.id} className="mt-2 flex items-center gap-1 text-[12px]"><Paperclip size={12} />{file.original_name}</p>)}
                                            {(message.actions ?? []).map((action) => <AgentActionCard
                                                key={action.id} action={action} project={project} sources={message.sources}
                                                enabled={message.id === lastMessage?.id && !busy && !sending}
                                                pending={chat.decide.isPending}
                                                onDecision={(decision) => chat.decide.mutate({ id: conversationId!, actionId: action.id, decision })}
                                            />)}
                                            {message.sources?.length > 0 && <div className="mt-3 grid gap-2">
                                                {message.sources.filter((source) => !(message.actions ?? []).some((action) => actionSources(action).some((item) => item.source_id === source.source_id)))
                                                    .map((source) => <AgentEntityCard key={source.source_id} source={source} project={project} />)}
                                            </div>}

                                        </div>
                                    </div>
                                ))}
                                <div ref={endRef} />
                            </div>
                        )}
                    </div>

                    <form onSubmit={onSubmit} className="border-t border-line-subtle bg-surface/55 px-4 py-3">
                        {chatError && <ErrorMessage title="Не удалось обновить диалог" message={(chatError as Error).message} />}
                        {selectedFiles.length > 0 && <ul className="mx-auto mb-2 flex max-w-3xl flex-wrap gap-2 text-[12px]">{selectedFiles.map((file) => <li key={file.id} className="rounded border border-line p-1">
                            {file.original_name} <button type="button" aria-label={`Убрать ${file.original_name}`} disabled={sending || busy} onClick={() => void removeFile(file.id)}>×</button>
                        </li>)}</ul>}
                        <div className="material-metal mx-auto flex max-w-3xl items-end gap-2 rounded-[var(--radius-card)] border border-ai-border p-2 transition-[border-color,box-shadow] focus-within:border-ai-blue/55 focus-within:shadow-focus">
                            <input type="file" multiple ref={fileInputRef} aria-label="Файлы для агента" className="hidden" onChange={(event) => { void uploadFiles(Array.from(event.target.files ?? [])); event.target.value = ""; }} />
                            <Button type="button" size="sm" disabled={sending || busy || loading || selectedFiles.length >= 5} title="Добавить файл до 10 МБ" onClick={() => fileInputRef.current?.click()} icon={<Paperclip size={14} />}>Файл</Button>
                            <textarea
                                value={question}
                                onChange={(event) => updateDraft(draftKey, { content: event.target.value })}
                                onKeyDown={onKeyDown}
                                rows={2}
                                maxLength={2000}
                                placeholder="Спросите о проекте…"
                                aria-label="Вопрос агенту"
                                disabled={sending || busy || loading}
                                className="scrollbar-thin min-h-10 min-w-0 flex-1 resize-none bg-transparent px-1.5 py-1 text-[13px] text-primary outline-none placeholder:text-disabled"
                            />
                            <Button
                                type="submit"
                                variant="primary"
                                size="md"
                                disabled={question.trim().length < 2 || sending || busy || loading || chat.messages.isError}
                                icon={<Send size={14} aria-hidden="true" />}
                            >
                                <span className={compact ? "sr-only" : undefined}>Спросить</span>
                            </Button>
                        </div>
                        <p className="mx-auto mt-1.5 max-w-3xl text-[10px] text-disabled">
                            Переписка сохраняется. Enter — отправить, Shift+Enter — новая строка.
                        </p>
                    </form>
                </section>

                {!compact && <aside className="scrollbar-thin hidden min-h-0 flex-col gap-3 overflow-y-auto lg:flex">
                    <section className="flex flex-col gap-3 rounded-[var(--radius-card)] bg-surface/55 p-4">
                        <div className="flex items-center gap-2 text-[13px] font-semibold text-secondary">
                            <Database size={14} aria-hidden="true" />
                        Знания проекта
                        </div>
                        {statusQuery.error ? (
                            <p className="text-[12px] text-danger">
                                {(statusQuery.error as Error).message}
                            </p>
                        ) : (
                            <dl className="flex flex-col gap-2 text-[12px]">
                                <div className="flex justify-between gap-3">
                                    <dt className="text-muted">Фрагментов</dt>
                                    <dd className="font-mono text-secondary">
                                        {status?.points_count ?? "—"}
                                    </dd>
                                </div>
                                <div className="flex justify-between gap-3">
                                    <dt className="text-muted">В очереди</dt>
                                    <dd className="font-mono text-secondary">
                                        {(status?.pending_jobs ?? 0) + (status?.processing_jobs ?? 0)}
                                    </dd>
                                </div>
                                <div className="flex justify-between gap-3">
                                    <dt className="text-muted">Ошибок</dt>
                                    <dd className={cn("font-mono", status?.failed_jobs ? "text-danger" : "text-secondary")}>
                                        {status?.failed_jobs ?? 0}
                                    </dd>
                                </div>
                            </dl>
                        )}
                        {status?.last_error && (
                            <p className="line-clamp-4 rounded-md bg-danger/8 p-2 text-[11px] text-danger">
                                {status.last_error}
                            </p>
                        )}
                        <Button
                            size="sm"
                            onClick={() => reindexMutation.mutate()}
                            disabled={reindexMutation.isPending || indexing}
                            icon={
                                <RefreshCw
                                    size={13}
                                    className={reindexMutation.isPending ? "animate-spin" : undefined}
                                />
                            }
                        >
                            Переиндексировать
                        </Button>
                    </section>
                    {Boolean(status?.coverage?.length) && (
                        <section className="rounded-[var(--radius-card)] bg-surface/55 p-4 text-[12px]">
                            <p className="mb-2 font-medium text-secondary">Доступно для поиска</p>
                            <dl className="flex flex-col gap-1.5">
                                {status?.coverage.map((row) => (
                                    <div key={row.entity_type} className="flex justify-between gap-2">
                                        <dt className="text-muted">{SOURCE_LABELS[row.entity_type]}</dt>
                                        <dd className={cn("font-mono", row.missing || row.stale ? "text-warning" : "text-secondary")}>
                                            {row.indexed} / {row.total}
                                        </dd>
                                    </div>
                                ))}
                            </dl>
                            {Boolean(status?.file_issues?.length) && (
                                <div className="mt-3 space-y-2 text-warning">
                                    <p>Не весь текст файлов доступен:</p>
                                    {status?.file_issues.map((issue) => (
                                        <p key={issue.source_id}><span className="font-medium">{issue.title}</span>: {issue.detail || "Ожидает обработки"}</p>
                                    ))}
                                </div>
                            )}
                        </section>
                    )}
                    <section className="border-t border-line-subtle px-1 pt-4 text-[12px] leading-relaxed text-muted">
                        <p className="mb-2 font-medium text-secondary">Что знает агент</p>
                        <ul className="flex list-disc flex-col gap-1 pl-4">
                            <li>паспорт, команда, стадии и структура проекта;</li>
                            <li>задачи, чек-листы, риски, вехи и стикеры;</li>
                            <li>документы, комментарии и извлечённый текст файлов;</li>
                            <li>связи объектов, история изменений и сохранённые отчёты.</li>
                        </ul>
                    </section>
                </aside>}
            </div>
        </div>
    );
}
