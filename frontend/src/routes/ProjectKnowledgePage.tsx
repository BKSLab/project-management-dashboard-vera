import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
    Bot,
    ShieldAlert,
    Database,
    Diamond,
    FileText,
    ListTodo,
    MessageSquare,
    Paperclip,
    RefreshCw,
    Send,
    Sparkles,
} from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type {
    KnowledgeAnswer,
    KnowledgeAskPayload,
    KnowledgeChatMessage,
    Project,
    KnowledgeSource,
    KnowledgeStatus,
} from "@/lib/types";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { useRenderedMarkdown } from "@/lib/useRenderedMarkdown";
import { useUiStore } from "@/stores/ui";
import { Button } from "@/components/ui/Button";
import { ErrorMessage } from "@/components/ui/States";
import { cn } from "@/lib/cn";

const STARTERS = [
    "Дай краткую сводку проекта и текущие риски",
    "Какие задачи просрочены и кто за них отвечает?",
    "Что уже сделано, а что сейчас в работе?",
    "Какие решения и требования зафиксированы в документах?",
];

interface UiMessage extends KnowledgeChatMessage {
    id: string;
    sources?: KnowledgeSource[];
}

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

function sourceIcon(source: KnowledgeSource) {
    if (source.entity_type === "risk") return <ShieldAlert size={13} />;
    if (source.entity_type === "document") return <FileText size={13} />;
    if (source.entity_type === "comment") return <MessageSquare size={13} />;
    if (source.entity_type === "attachment") return <Paperclip size={13} />;
    if (source.entity_type === "task") return <ListTodo size={13} />;
    if (source.entity_type === "milestone") return <Diamond size={13} />;
    return <Database size={13} />;
}

export function ProjectKnowledgePage() {
    const project = useProjectOutlet();
    return <ProjectKnowledgeWorkspace key={project.id} project={project} />;
}

function ProjectKnowledgeWorkspace({ project }: { project: Project }) {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);
    const endRef = useRef<HTMLDivElement>(null);
    const [question, setQuestion] = useState("");
    const [messages, setMessages] = useState<UiMessage[]>([]);

    const statusQuery = useQuery({
        queryKey: queryKeys.projectKnowledgeStatus(project.id),
        queryFn: () =>
            api.get<KnowledgeStatus>(endpoints.projectKnowledgeStatus(project.id)),
        refetchInterval: 3000,
    });

    const askMutation = useMutation({
        mutationFn: (payload: KnowledgeAskPayload) =>
            api.post<KnowledgeAnswer>(endpoints.projectKnowledgeAsk(project.id), payload),
        onSuccess: (answer) => {
            setMessages((current) => [
                ...current,
                {
                    id: crypto.randomUUID(),
                    role: "assistant",
                    content: answer.answer,
                    sources: answer.sources,
                },
            ]);
        },
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
    }, [messages, askMutation.isPending]);

    function submit(value = question) {
        const normalized = value.trim();
        if (!normalized || askMutation.isPending) return;
        const history = messages.slice(-10).map(({ role, content }) => ({ role, content }));
        setMessages((current) => [
            ...current,
            { id: crypto.randomUUID(), role: "user", content: normalized },
        ]);
        setQuestion("");
        askMutation.reset();
        askMutation.mutate({ question: normalized, history });
    }

    function onSubmit(event: FormEvent) {
        event.preventDefault();
        submit();
    }

    function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
        }
    }

    function openSource(source: KnowledgeSource) {
        if (source.entity_type === "risk") {
            useUiStore.getState().setSelectedRisk({ projectId: project.id, riskId: source.entity_id });
            return;
        }
        if (source.task_id !== null) {
            setSelectedTaskId(source.task_id);
            return;
        }
        if (source.document_slug) {
            navigate(`/projects/${project.key}/docs/${source.document_slug}`);
            return;
        }
        if (source.entity_type === "milestone") {
            navigate(`/projects/${project.key}/calendar`);
            return;
        }
        navigate(`/projects/${project.key}`);
    }

    const status = statusQuery.data;
    const indexing = Boolean(status && (status.pending_jobs > 0 || status.processing_jobs > 0));

    return (
        <div className="h-full min-h-0">
            <div className="mx-auto grid h-full w-full max-w-6xl gap-4 p-5 lg:grid-cols-[minmax(0,1fr)_280px]">
                <section className="ai-surface flex min-h-0 flex-col overflow-hidden rounded-[var(--radius-panel)] border border-ai-border shadow-card">
                    <div className="flex items-center justify-between gap-3 border-b border-line-subtle px-4 py-3">
                        <div className="flex min-w-0 items-center gap-2.5">
                            <span className="ai-mark flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-control)] text-ai-blue">
                                <Bot size={17} aria-hidden="true" />
                            </span>
                            <div className="min-w-0">
                                <h2 className="text-[13px] font-semibold text-primary">Project Agent</h2>
                                <p className="truncate text-[11px] text-muted">
                                    Отвечает по задачам, документам и файлам проекта
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
                            {status?.ready ? "Вики готова" : indexing ? "Индексация" : "SQL-режим"}
                        </span>
                    </div>

                    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-4 py-5">
                        {messages.length === 0 ? (
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
                                <div className="grid w-full border-y border-line-subtle sm:grid-cols-2">
                                    {STARTERS.map((starter) => (
                                        <button
                                            key={starter}
                                            type="button"
                                            onClick={() => submit(starter)}
                                            className="px-3 py-2.5 text-left text-[12px] text-secondary transition-colors hover:bg-ai-soft hover:text-primary sm:odd:border-r sm:odd:border-line-subtle"
                                        >
                                            {starter}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="mx-auto flex max-w-3xl flex-col gap-4">
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
                                                "max-w-[88%] rounded-lg px-3.5 py-3",
                                                message.role === "user"
                                                    ? "bg-accent/85 text-on-accent"
                                                    : "bg-ai-soft text-secondary shadow-card",
                                            )}
                                        >
                                            {message.role === "assistant" ? (
                                                <MarkdownAnswer content={message.content} />
                                            ) : (
                                                <p className="whitespace-pre-wrap text-[13px] leading-relaxed">
                                                    {message.content}
                                                </p>
                                            )}
                                            {message.sources && message.sources.length > 0 && (
                                                <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line-subtle pt-2.5">
                                                    {message.sources.map((source) => (
                                                        <button
                                                            key={source.source_id}
                                                            type="button"
                                                            title={source.excerpt ?? source.title}
                                                            onClick={() => openSource(source)}
                                                            className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-line bg-surface px-2 py-1 text-[11px] text-muted hover:border-accent-border hover:text-accent"
                                                        >
                                                            {sourceIcon(source)}
                                                            <span className="truncate">{source.title}</span>
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                                {askMutation.isPending && (
                                    <div className="flex items-center gap-2 text-[12px] text-muted">
                                        <RefreshCw size={13} className="animate-spin" />
                                        Агент сверяет источники…
                                    </div>
                                )}
                                {askMutation.error && (
                                    <ErrorMessage
                                        title="Агент не ответил"
                                        message={(askMutation.error as Error).message}
                                    />
                                )}
                                <div ref={endRef} />
                            </div>
                        )}
                    </div>

                    <form onSubmit={onSubmit} className="border-t border-line-subtle bg-surface/55 px-4 py-3">
                        <div className="material-metal mx-auto flex max-w-3xl items-end gap-2 rounded-[var(--radius-card)] border border-ai-border p-2 transition-[border-color,box-shadow] focus-within:border-ai-blue/55 focus-within:shadow-focus">
                            <textarea
                                value={question}
                                onChange={(event) => setQuestion(event.target.value)}
                                onKeyDown={onKeyDown}
                                rows={2}
                                maxLength={2000}
                                placeholder="Спросите о проекте…"
                                aria-label="Вопрос Project Agent"
                                className="scrollbar-thin min-h-10 flex-1 resize-none bg-transparent px-1.5 py-1 text-[13px] text-primary outline-none placeholder:text-disabled"
                            />
                            <Button
                                type="submit"
                                variant="primary"
                                size="md"
                                disabled={!question.trim() || askMutation.isPending}
                                icon={<Send size={14} aria-hidden="true" />}
                            >
                                Спросить
                            </Button>
                        </div>
                        <p className="mx-auto mt-1.5 max-w-3xl text-[10px] text-disabled">
                            Enter — отправить, Shift+Enter — новая строка. Проверяйте важные решения по источникам.
                        </p>
                    </form>
                </section>

                <aside className="scrollbar-thin hidden min-h-0 flex-col gap-3 overflow-y-auto lg:flex">
                    <section className="flex flex-col gap-3 rounded-[var(--radius-card)] bg-surface/55 p-4">
                        <div className="flex items-center gap-2 text-[13px] font-semibold text-secondary">
                            <Database size={14} aria-hidden="true" />
                            AI-вики
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
                    <section className="border-t border-line-subtle px-1 pt-4 text-[12px] leading-relaxed text-muted">
                        <p className="mb-2 font-medium text-secondary">Что знает агент</p>
                        <ul className="flex list-disc flex-col gap-1 pl-4">
                            <li>описание и структура проекта;</li>
                            <li>задачи, сроки, стадии и исполнители;</li>
                            <li>вики-документы и комментарии;</li>
                            <li>текст PDF, DOCX, Markdown и TXT-вложений.</li>
                        </ul>
                    </section>
                </aside>
            </div>
        </div>
    );
}
