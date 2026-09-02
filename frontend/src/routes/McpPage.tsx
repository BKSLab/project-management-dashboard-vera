import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, KeyRound, Plug, Trash2 } from "lucide-react";
import { api, authEndpoints, queryKeys } from "@/lib/api";
import { formatFullDate } from "@/lib/dates";
import {
    buildMcpConfig,
    mcpServerUrl,
    scopeLabel,
    tokenState,
    toolsForScope,
} from "@/lib/mcpConfig";
import { useToast } from "@/lib/toast";
import type {
    ApiToken,
    ApiTokenCreated,
    ApiTokenCreatePayload,
    ApiTokenScope,
} from "@/lib/types";
import { Page } from "@/components/layout/AppShell";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, Section } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { EmptyState, ErrorMessage, Skeleton } from "@/components/ui/States";

const TTL_OPTIONS = [
    { value: "30", label: "30 дней" },
    { value: "90", label: "90 дней" },
    { value: "365", label: "год" },
    { value: "", label: "без срока" },
];

function CopyButton({ value, label }: { value: string; label: string }) {
    const [copied, setCopied] = useState(false);
    const toast = useToast();

    async function copy() {
        try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 2000);
        } catch {
            toast.error("Не удалось скопировать: разрешите доступ к буферу обмена");
        }
    }

    return (
        <Button variant="secondary" onClick={copy} aria-label={label}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            {copied ? "Скопировано" : "Копировать"}
        </Button>
    );
}

export function McpPage() {
    const queryClient = useQueryClient();
    const toast = useToast();
    const [name, setName] = useState("");
    const [scope, setScope] = useState<ApiTokenScope>("READ");
    const [ttl, setTtl] = useState("90");
    const [issued, setIssued] = useState<ApiTokenCreated | null>(null);

    const origin = typeof window === "undefined" ? "" : window.location.origin;
    const serverUrl = useMemo(() => mcpServerUrl(origin), [origin]);
    const configSnippet = useMemo(
        () => buildMcpConfig({ origin, secret: issued?.secret }),
        [origin, issued],
    );

    const tokensQuery = useQuery({
        queryKey: queryKeys.apiTokens,
        queryFn: () => api.get<ApiToken[]>(authEndpoints.apiTokens()),
    });

    const createMutation = useMutation({
        mutationFn: (payload: ApiTokenCreatePayload) =>
            api.post<ApiTokenCreated>(authEndpoints.apiTokens(), payload),
        onSuccess: (created) => {
            setIssued(created);
            setName("");
            void queryClient.invalidateQueries({ queryKey: queryKeys.apiTokens });
            toast.success("Токен выпущен — скопируйте его сейчас");
        },
        onError: (error: Error) => toast.error(error.message),
    });

    const revokeMutation = useMutation({
        mutationFn: (tokenId: number) => api.delete<void>(authEndpoints.apiToken(tokenId)),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: queryKeys.apiTokens });
            toast.success("Токен отозван");
        },
        onError: (error: Error) => toast.error(error.message),
    });

    function submit(event: React.FormEvent) {
        event.preventDefault();
        if (!name.trim()) {
            return;
        }
        createMutation.mutate({
            name: name.trim(),
            scope,
            ttl_days: ttl === "" ? null : Number(ttl),
        });
    }

    function revoke(token: ApiToken) {
        const confirmed = window.confirm(
            `Отозвать токен «${token.name}»? Клиенты, использующие его, потеряют доступ.`,
        );
        if (confirmed) {
            revokeMutation.mutate(token.id);
        }
    }

    return (
        <Page>
            <header className="flex flex-col gap-1">
                <h1 className="flex items-center gap-2 text-lg font-semibold text-primary">
                    <Plug className="size-4 text-accent" />
                    MCP
                </h1>
                <p className="text-[13px] text-secondary">
                    Подключите трекер к AI-агенту: он сможет вести задачи, читать комментарии
                    и искать по проектам от вашего имени.
                </p>
            </header>

            <Section title="Подключение">
                <Card className="flex flex-col gap-3 p-4">
                    <p className="text-[13px] text-secondary">
                        Адрес сервера:{" "}
                        <code className="rounded bg-hover px-1.5 py-0.5 text-primary">
                            {serverUrl}
                        </code>
                    </p>
                    {issued === null && (
                        <p className="text-[13px] text-secondary">
                            Выпустите токен ниже — он подставится в конфигурацию автоматически.
                            Сейчас на его месте плейсхолдер.
                        </p>
                    )}
                    <pre className="scrollbar-thin overflow-x-auto rounded-md border border-line bg-sidebar p-3 text-[12px] leading-relaxed text-primary">
                        {configSnippet}
                    </pre>
                    <div className="flex justify-end">
                        <CopyButton value={configSnippet} label="Скопировать конфигурацию" />
                    </div>
                </Card>
            </Section>

            {issued !== null && (
                <Section title="Новый токен">
                    <Card className="flex flex-col gap-3 border-accent/40 p-4">
                        <p className="text-[13px] font-medium text-primary">
                            Скопируйте токен сейчас: показать его повторно невозможно.
                        </p>
                        <code className="break-all rounded-md border border-line bg-sidebar p-3 text-[13px] text-accent">
                            {issued.secret}
                        </code>
                        <div className="flex justify-end gap-2">
                            <CopyButton value={issued.secret} label="Скопировать токен" />
                            <Button variant="ghost" onClick={() => setIssued(null)}>
                                Я сохранил
                            </Button>
                        </div>
                    </Card>
                </Section>
            )}

            <Section title="Выпустить токен">
                <Card className="p-4">
                    <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={submit}>
                        <Field label="Название" className="flex-1">
                            {(id) => (
                                <Input
                                    id={id}
                                    value={name}
                                    onChange={(event) => setName(event.target.value)}
                                    placeholder="Ноутбук"
                                    maxLength={100}
                                    required
                                />
                            )}
                        </Field>
                        <Field label="Права">
                            {(id) => (
                                <Select
                                    id={id}
                                    value={scope}
                                    onChange={(event) =>
                                        setScope(event.target.value as ApiTokenScope)
                                    }
                                >
                                    <option value="READ">Только чтение</option>
                                    <option value="WRITE">Чтение и запись</option>
                                </Select>
                            )}
                        </Field>
                        <Field label="Срок">
                            {(id) => (
                                <Select
                                    id={id}
                                    value={ttl}
                                    onChange={(event) => setTtl(event.target.value)}
                                >
                                    {TTL_OPTIONS.map((option) => (
                                        <option key={option.label} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </Select>
                            )}
                        </Field>
                        <Button type="submit" disabled={createMutation.isPending}>
                            <KeyRound className="size-3.5" />
                            Выпустить
                        </Button>
                    </form>
                    <p className="mt-3 text-[12px] text-secondary">
                        Токен на запись позволяет агенту создавать, изменять и удалять задачи.
                        Если нужны только сводки и поиск — оставьте «только чтение».
                    </p>
                </Card>
            </Section>

            <Section title="Что разрешает токен">
                <Card className="flex flex-col gap-3 p-4">
                    <div>
                        <p className="text-[13px] font-medium text-primary">Только чтение</p>
                        <p className="text-[12px] text-secondary">
                            {toolsForScope("READ").join(", ")}
                        </p>
                    </div>
                    <div>
                        <p className="text-[13px] font-medium text-primary">Дополнительно с записью</p>
                        <p className="text-[12px] text-secondary">
                            create_task, update_task, move_task, delete_task, add_comment
                        </p>
                    </div>
                    <p className="text-[12px] text-secondary">
                        Токен видит только те проекты, в которых вы состоите. Управлять самими
                        токенами через MCP нельзя — только на этой странице.
                    </p>
                </Card>
            </Section>

            <Section title="Выпущенные токены">
                {tokensQuery.isPending && <Skeleton className="h-24 w-full" />}
                {tokensQuery.isError && (
                    <ErrorMessage
                        title="Не удалось загрузить токены"
                        message={(tokensQuery.error as Error).message}
                    />
                )}
                {tokensQuery.data?.length === 0 && (
                    <EmptyState
                        title="Токенов пока нет"
                        description="Выпустите первый токен, чтобы подключить агента."
                        icon={<KeyRound className="size-5" />}
                    />
                )}
                {tokensQuery.data !== undefined && tokensQuery.data.length > 0 && (
                    <Card className="divide-y divide-line p-0">
                        {tokensQuery.data.map((token) => {
                            const state = tokenState(token);
                            return (
                                <div
                                    key={token.id}
                                    className="flex items-center justify-between gap-3 px-4 py-3"
                                >
                                    <div className="min-w-0">
                                        <p className="truncate text-[13px] text-primary">
                                            {token.name}{" "}
                                            <code className="text-secondary">{token.prefix}…</code>
                                        </p>
                                        <p className="text-[12px] text-secondary">
                                            {scopeLabel(token.scope)} · {state} · создан{" "}
                                            {formatFullDate(token.created_at)}
                                            {token.last_used_at !== null &&
                                                ` · использован ${formatFullDate(token.last_used_at)}`}
                                        </p>
                                    </div>
                                    {token.revoked_at === null && (
                                        <IconButton
                                            label={`Отозвать токен ${token.name}`}
                                            onClick={() => revoke(token)}
                                            disabled={revokeMutation.isPending}
                                        >
                                            <Trash2 className="size-3.5" />
                                        </IconButton>
                                    )}
                                </div>
                            );
                        })}
                    </Card>
                )}
            </Section>
        </Page>
    );
}
