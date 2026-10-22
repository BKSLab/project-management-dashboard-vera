import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Eye, Paperclip, Plus, Send, X } from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { AgentMessage, Project, Task } from "@/lib/types";
import { useTimConversations } from "@/lib/useTimConversations";
import { describePageContext, TIM_NAME, TIM_PERSONA } from "@/lib/tim";
import { useTimPageContext } from "@/lib/useTimPageContext";
import { actionSources } from "@/lib/agentCards";
import { cn } from "@/lib/cn";
import { useTimWidgetStore } from "@/stores/timWidget";
import { Button, IconButton } from "@/components/ui/Button";
import { ErrorMessage } from "@/components/ui/States";
import { AgentActionCard } from "@/components/projects/AgentActionCard";
import { AgentEntityCard } from "@/components/agent/AgentEntityCard";
import { TimMarkdown, TimThinking } from "@/components/chat/TimChatReply";
import { newUuid } from "@/lib/uuid";
import { TimAvatar } from "./TimAvatar";

/** Панель личного диалога с Верой (docs/tim-agent.md, 3). */
export function TimPanel({ userId, onClose }: { userId: number; onClose: () => void }) {
    const context = useTimPageContext();
    const projects = useQuery({ queryKey: queryKeys.projects, queryFn: () => api.get<Project[]>(endpoints.projects()) }).data ?? [];
    const task = useQuery({ queryKey: queryKeys.task(context.task_id ?? 0), queryFn: () => api.get<Task>(endpoints.task(context.task_id!)), enabled: context.task_id != null }).data;
    const pageProject = context.project_key ? projects.find((item) => item.key.toUpperCase() === context.project_key!.toUpperCase()) : undefined;
    const seen = describePageContext(context, { project: pageProject?.key, taskKey: task?.id === context.task_id ? task?.key : null });

    const remembered = useTimWidgetStore((state) => state.conversations[userId]);
    const select = useTimWidgetStore((state) => state.select);
    const updateDraft = useTimWidgetStore((state) => state.updateDraft);
    const clearDraft = useTimWidgetStore((state) => state.clearDraft);
    const chat = useTimConversations(remembered ?? null);
    const conversations = chat.conversations.data?.pages.flatMap((page) => page.items) ?? [];
    const firstId = conversations[0]?.id;
    // Текущий диалог — первый в списке сервера, пока пользователь не выбрал другой.
    const conversationId = remembered ?? firstId ?? null;
    useEffect(() => { if (remembered == null && firstId != null) select(userId, firstId); }, [remembered, firstId, select, userId]);
    const messages = chat.messages.data?.pages.slice().reverse().flatMap((page) => page.items) ?? [];
    const draftKey = `${userId}:${conversationId ?? "new"}`;
    const draft = useTimWidgetStore((state) => state.drafts[draftKey]);
    const question = draft?.content ?? "";
    const selectedFiles = draft?.files ?? [];
    const busy = messages.some((message) => message.status === "queued" || message.status === "processing");
    const sending = chat.mutating;
    const sendingRef = useRef(false);
    const loading = chat.conversations.isPending || (conversationId != null && chat.messages.isPending);
    const chatError = chat.conversations.error || chat.messages.error || chat.create.error || chat.send.error || chat.retry.error || chat.decide.error || chat.upload.error || chat.removeUpload.error;
    const lastMessage = messages.at(-1);
    const panel = useRef<HTMLElement>(null);
    const endRef = useRef<HTMLDivElement>(null);
    const input = useRef<HTMLTextAreaElement>(null);
    const fileInput = useRef<HTMLInputElement>(null);
    useEffect(() => { input.current?.focus(); }, []);
    useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [conversationId, lastMessage?.id, lastMessage?.status]);

    function resetErrors() {
        chat.send.reset(); chat.retry.reset(); chat.decide.reset(); chat.upload.reset(); chat.removeUpload.reset(); chat.create.reset();
    }
    function choose(id: number) { select(userId, id); resetErrors(); }

    async function ensureConversation(): Promise<number> {
        if (conversationId != null) return conversationId;
        const id = (await chat.create.mutateAsync()).id;
        select(userId, id);
        return id;
    }

    async function submit(value = question) {
        const normalized = value.trim();
        if (normalized.length < 2 || sending || sendingRef.current || busy || loading || chat.messages.isError) return;
        sendingRef.current = true;
        const requestId = draft?.content.trim() === normalized ? draft.requestId : newUuid();
        updateDraft(draftKey, { content: normalized, files: selectedFiles, requestId });
        try {
            const id = await ensureConversation();
            const key = `${userId}:${id}`;
            if (key !== draftKey) { updateDraft(key, { content: normalized, files: selectedFiles, requestId }); clearDraft(draftKey, requestId); }
            await chat.send.mutateAsync({ id, content: normalized, requestId, fileIds: selectedFiles.map((file) => file.id), pageContext: context });
            clearDraft(key, requestId);
        } catch {
            // Черновик и UUID остаются: повтор не создаст второй вопрос.
        } finally {
            sendingRef.current = false;
        }
    }

    async function newConversation() {
        if (sending || sendingRef.current) return;
        sendingRef.current = true;
        try { choose((await chat.create.mutateAsync()).id); } catch { /* Ошибка показывается над полем ввода. */ } finally { sendingRef.current = false; }
    }

    async function uploadFiles(files: File[]) {
        if (sending || sendingRef.current || busy || loading) return;
        sendingRef.current = true;
        try {
            const id = await ensureConversation();
            const key = `${userId}:${id}`;
            if (key !== draftKey) updateDraft(key, { content: question, files: selectedFiles });
            for (const file of files.slice(0, 5 - selectedFiles.length)) {
                const uploaded = await chat.upload.mutateAsync({ id, file });
                updateDraft(key, { files: [...(useTimWidgetStore.getState().drafts[key]?.files ?? []), uploaded] });
            }
        } catch { /* Загруженные файлы остаются, ошибка — над полем ввода. */ } finally { sendingRef.current = false; }
    }

    async function removeFile(fileId: string) {
        if (conversationId == null || sending || busy) return;
        try {
            await chat.removeUpload.mutateAsync({ id: conversationId, fileId });
            updateDraft(draftKey, { files: (useTimWidgetStore.getState().drafts[draftKey]?.files ?? []).filter((file) => file.id !== fileId) });
        } catch { /* Ошибка показывается над полем ввода. */ }
    }

    function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit(); }
    }

    /** Проект карточек ответа — со страницы, откуда задан вопрос (у ответа контекста нет). */
    function answerProject(message: AgentMessage) {
        const asked = messages.find((item) => item.role === "user" && item.request_id === message.request_id);
        const key = asked?.page_context?.project_key;
        const project = key ? projects.find((item) => item.key.toUpperCase() === key.toUpperCase()) : undefined;
        return project ? { id: project.id, key: project.key } : null;
    }

    const boardStarters = context.board_selection?.length
        ? ["Выровняй выделенные объекты по верхнему краю", "Перестрой выделенную схему слева направо"]
        : ["Кратко опиши схему на этой доске", "Что можно улучшить в этой схеме?"];
    const starters = context.board_id ? boardStarters : [
        ...(context.task_id ? ["Что с этой задачей и что мешает её закрыть?"] : []),
        ...(context.project_key && !context.task_id ? ["Дай сводку по этому проекту: сроки и риски"] : []),
        "Какие мои задачи просрочены или горят на этой неделе?",
        "Что у меня в работе и что стоит сделать первым?",
    ];

    return <section ref={panel} role="dialog" aria-modal="false" aria-label={TIM_PERSONA} tabIndex={-1} className="tt-tim-panel"
        onKeyDown={(event) => { if (event.key === "Escape" && !event.defaultPrevented) { event.preventDefault(); event.stopPropagation(); onClose(); } }}>
        <header className="material-glass flex shrink-0 items-center gap-2 border-b border-line-subtle px-3 py-2.5">
            <TimAvatar />
            <div className="min-w-0 flex-1">
                <h2 className="text-[13px] font-semibold text-primary">{TIM_NAME}<span className="font-normal text-muted"> — проектный менеджер</span></h2>
                <p className="flex min-w-0 items-center gap-1 text-[11px] text-muted" data-testid="tim-context"
                    title={seen ? "Вера учитывает эту страницу: можно спросить «что с этой задачей?»" : "Вера видит ваши задачи и проекты, в которых вы участвуете"}>
                    <Eye size={11} className="shrink-0" aria-hidden="true" />
                    <span className="truncate">{seen || "Личный помощник: ваши задачи и проекты"}</span>
                </p>
            </div>
            <IconButton label="Новый диалог с Верой — прежние останутся в списке" disabled={sending || loading} onClick={() => void newConversation()}><Plus size={16} /></IconButton>
            <IconButton label="Закрыть окно Веры" onClick={onClose}><X size={16} /></IconButton>
        </header>

        {conversations.length > 0 && <div className="flex shrink-0 items-center gap-2 border-b border-line-subtle px-3 py-1.5">
            <select aria-label="Диалог с Верой" title="Прежние диалоги с Верой — от недавних к старым" value={conversationId ?? ""} disabled={sending} onChange={(event) => choose(Number(event.target.value))}
                className="min-w-0 flex-1 rounded-[var(--radius-control)] border border-line bg-surface px-2 py-1 text-[12px] text-primary">
                {conversationId != null && !conversations.some((item) => item.id === conversationId) && <option value={conversationId}>Текущий диалог</option>}
                {conversations.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
            </select>
            {chat.conversations.hasNextPage && <Button size="sm" variant="ghost" disabled={chat.conversations.isFetchingNextPage} onClick={() => void chat.conversations.fetchNextPage()}>Ещё</Button>}
        </div>}

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-4" aria-live="polite">
            {loading ? <p className="text-[13px] text-muted">Загружаю переписку…</p> : messages.length === 0 ? (
                <div className="flex flex-col gap-3 py-4 text-center">
                    <p className="text-[13px] text-secondary">Спросите Веру о своих задачах, сроках и проектах. Обращаться «Вера, …» здесь не нужно — этот диалог видите только вы.</p>
                    <div className="grid border-y border-line-subtle">
                        {starters.map((starter) => <button key={starter} type="button" disabled={sending || Boolean(chatError)} onClick={() => void submit(starter)}
                            className="px-3 py-2 text-left text-[12px] text-secondary transition-colors hover:bg-ai-soft hover:text-primary">{starter}</button>)}
                    </div>
                </div>
            ) : <div className="flex flex-col gap-3">
                {chat.messages.hasNextPage && <Button size="sm" variant="ghost" disabled={chat.messages.isFetchingNextPage} onClick={() => void chat.messages.fetchNextPage()}>Предыдущие сообщения</Button>}
                {messages.map((message) => {
                    const project = message.role === "assistant" ? answerProject(message) : null;
                    const actions = message.actions ?? [];
                    const asked = message.role === "user" && message.page_context ? describePageContext(message.page_context) : "";
                    return <div key={message.id} className={cn("flex gap-2", message.role === "user" ? "justify-end" : "justify-start")}>
                        {message.role === "assistant" && <TimAvatar className="mt-1" />}
                        <div data-role={message.role} className={cn("min-w-0 max-w-[92%] rounded-lg px-3 py-2.5", message.role === "user" ? "bg-accent/85 text-on-accent" : "tt-tim-message text-secondary")}>
                            {message.status === "queued" || message.status === "processing" ? <TimThinking progress={message.progress} />
                                : message.status === "failed" ? <div className="space-y-2 text-[12px]">
                                    <p className="text-danger">{message.error || "Не получилось ответить."}</p>
                                    {message.id === lastMessage?.id && <Button size="sm" disabled={sending} title="Вера попробует ответить на тот же вопрос ещё раз" onClick={() => chat.retry.mutate({ id: conversationId!, messageId: message.id })}>Повторить</Button>}
                                </div>
                                : message.role === "assistant" ? (message.content.trim() ? <TimMarkdown content={message.content} /> : null)
                                : <p className="whitespace-pre-wrap text-[13px] leading-relaxed">{message.content}</p>}
                            {asked && <p className="mt-1 text-[10px] opacity-75" title="Страница, с которой задан вопрос — её видела Вера">{asked}</p>}
                            {(message.files ?? []).map((file) => <p key={file.id} className="mt-2 flex items-center gap-1 text-[12px]"><Paperclip size={12} />{file.original_name}</p>)}
                            {actions.map((action) => <AgentActionCard key={action.id} action={action} project={project} sources={message.sources}
                                pending={chat.decide.isPending && chat.decide.variables?.actionId === action.id}
                                onDecision={(decision) => chat.decide.mutate({ id: conversationId!, actionId: action.id, decision })}
                                rules={{ enabled: message.id === lastMessage?.id && !busy && !sending, approveHint: "Выполнить от вашего имени. Отменить можно только вручную" }}
                            />)}
                            {message.sources?.length > 0 && <div className="mt-2 grid gap-2">
                                {message.sources.filter((source) => !actions.some((action) => actionSources(action).some((item) => item.source_id === source.source_id)))
                                    .map((source) => <AgentEntityCard key={source.source_id} source={source} project={project} />)}
                            </div>}
                        </div>
                    </div>;
                })}
                <div ref={endRef} />
            </div>}
        </div>

        <form onSubmit={(event: FormEvent) => { event.preventDefault(); void submit(); }} className="shrink-0 border-t border-line-subtle px-3 py-2.5">
            {chatError && <ErrorMessage title="Вера сейчас недоступна" message={(chatError as Error).message} />}
            {selectedFiles.length > 0 && <ul className="mb-2 flex flex-wrap gap-1.5 text-[11px]">{selectedFiles.map((file) => <li key={file.id} className="flex items-center gap-1 rounded bg-sunken px-2 py-1 text-secondary">
                <Paperclip size={11} /><span className="max-w-40 truncate">{file.original_name}</span>
                <button type="button" aria-label={`Убрать ${file.original_name}`} title="Не отправлять этот файл" disabled={sending || busy} onClick={() => void removeFile(file.id)}><X size={11} /></button>
            </li>)}</ul>}
            <div className="flex items-end gap-1.5 rounded-[var(--radius-card)] border border-ai-border bg-surface p-1.5 focus-within:border-ai-blue/55">
                <input type="file" multiple ref={fileInput} aria-label="Файлы для Веры" className="hidden" onChange={(event) => { void uploadFiles(Array.from(event.target.files ?? [])); event.target.value = ""; }} />
                <IconButton label="Приложить файл для Веры: до 5 штук, до 10 МБ каждый" disabled={sending || busy || loading || selectedFiles.length >= 5} onClick={() => fileInput.current?.click()}><Paperclip size={15} /></IconButton>
                <textarea ref={input} value={question} rows={2} maxLength={2000}
                    onChange={(event) => updateDraft(draftKey, { content: event.target.value })} onKeyDown={onKeyDown}
                    placeholder={busy ? "Вера отвечает — дождитесь ответа, чтобы задать следующий вопрос" : "Спросите Веру о задачах, сроках, проектах…"} aria-label="Вопрос Вере"
                    disabled={sending || busy || loading}
                    className="scrollbar-thin min-h-9 min-w-0 flex-1 resize-none bg-transparent px-1 py-1 text-[13px] text-primary outline-none placeholder:text-faint" />
                <IconButton label="Отправить Вере (Enter)" variant="primary" type="submit" disabled={question.trim().length < 2 || sending || busy || loading || chat.messages.isError}><Send size={14} /></IconButton>
            </div>
            <p className="mt-1 text-[10px] text-muted">Видите только вы. Enter — отправить, Shift+Enter — новая строка. Изменения Вера выполняет по вашему поручению; опасные действия требуют подтверждения.</p>
        </form>
    </section>;
}
