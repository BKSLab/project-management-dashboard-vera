import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useUiStore } from "@/stores/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
    ROLE_COLORS,
    type WbsItem,
    type WbsNode as WbsNodeType,
    type WbsRole,
} from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorMessage } from "@/components/ui/ErrorMessage";

const STAGE_COLORS: Record<string, string> = {
    "Бэклог": "#999999",
    "К выполнению": "#3B82F6",
    "В работе": "#F5B800",
    "На проверке": "#A855F7",
    "Готово": "#22C55E",
};

const ROLE_OPTIONS: WbsRole[] = ["PM", "BE", "FE", "UXR", "UXD", "EXPERT", "QA", "BA", "MKT"];

interface WbsNodeProps {
    node: WbsNodeType;
    depth: number;
}

function ProgressBar({ done, total }: { done: number; total: number }) {
    const percent = total > 0 ? Math.round((done / total) * 100) : 0;
    return (
        <div className="flex items-center gap-2">
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-border">
                <div className="h-full rounded-full bg-accent" style={{ width: `${percent}%` }} />
            </div>
            <span className="text-xs text-muted">{done}/{total}</span>
        </div>
    );
}

function RoleBadge({ role }: { role: keyof typeof ROLE_COLORS }) {
    const color = ROLE_COLORS[role];
    return (
        <span
            className="rounded-full px-1.5 py-px text-[9px] font-semibold uppercase tracking-wider"
            style={{ color, backgroundColor: `${color}1A`, border: `1px solid ${color}4D` }}
        >
            {role}
        </span>
    );
}

interface ItemFormProps {
    initialTitle: string;
    initialRole: WbsRole | null;
    submitLabel: string;
    onSubmit: (title: string, role: WbsRole | null) => void;
    onCancel: () => void;
    isPending: boolean;
}

export function ItemForm({ initialTitle, initialRole, submitLabel, onSubmit, onCancel, isPending }: ItemFormProps) {
    const [title, setTitle] = useState(initialTitle);
    const [role, setRole] = useState<WbsRole | "">(initialRole ?? "");

    return (
        <div className="flex flex-wrap items-center gap-2 rounded border border-border bg-surface p-2">
            <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Название..."
                className="min-w-48 flex-1 rounded border border-border bg-background px-2 py-1 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            />
            <select
                value={role}
                onChange={(event) => setRole(event.target.value as WbsRole | "")}
                className="rounded border border-border bg-background px-2 py-1 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
                <option value="">Без роли</option>
                {ROLE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                ))}
            </select>
            <Button
                variant="primary"
                disabled={!title.trim() || isPending}
                onClick={() => onSubmit(title.trim(), role || null)}
            >
                {submitLabel}
            </Button>
            <Button variant="neutral" onClick={onCancel}>Отмена</Button>
        </div>
    );
}

export function WbsNode({ node, depth }: WbsNodeProps) {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const isExpanded = useUiStore((state) => state.wbsExpandedNodes.has(node.id));
    const toggle = useUiStore((state) => state.toggleWbsNode);

    const [isAddingChild, setIsAddingChild] = useState(false);
    const [isEditing, setIsEditing] = useState(false);

    const hasChildren = node.children.length > 0;
    const isLeaf = node.task !== null || (!hasChildren && node.progress === null);
    const stageColor = node.task ? STAGE_COLORS[node.task.stage_name] ?? "#999999" : undefined;

    const invalidateAll = () => {
        queryClient.invalidateQueries({ queryKey: ["wbs", "tree"] });
        queryClient.invalidateQueries({ queryKey: ["kanban", "tasks"] });
    };

    const createMutation = useMutation({
        mutationFn: (data: { title: string; role: WbsRole | null }) =>
            api.post<WbsItem>("/api/v1/wbs/items", { parent_id: node.id, title: data.title, role: data.role }),
        onSuccess: () => {
            invalidateAll();
            setIsAddingChild(false);
            if (!isExpanded) toggle(node.id);
        },
    });

    const updateMutation = useMutation({
        mutationFn: (data: { title: string; role: WbsRole | null }) =>
            api.patch<WbsItem>(`/api/v1/wbs/items/${node.id}`, { title: data.title, role: data.role }),
        onSuccess: () => {
            invalidateAll();
            setIsEditing(false);
        },
    });

    const deleteMutation = useMutation({
        mutationFn: () => api.delete(`/api/v1/wbs/items/${node.id}`),
        onSuccess: () => invalidateAll(),
    });

    const mutationError = createMutation.error ?? updateMutation.error ?? deleteMutation.error;

    const handleDelete = () => {
        const message = hasChildren
            ? `Удалить «${node.title}» вместе со всеми вложенными задачами и карточками канбана?`
            : `Удалить «${node.title}»? Связанная карточка канбана тоже будет удалена.`;
        if (window.confirm(message)) {
            deleteMutation.mutate();
        }
    };

    const isPhase = depth === 0;
    const isSection = depth === 1;

    return (
        <li>
            <div
                className={cn(
                    "group flex items-center gap-2 rounded px-2 py-1.5 hover:bg-surface-hover",
                    isPhase && "mt-2 border-t border-border pt-2 first:mt-0 first:border-t-0"
                )}
                style={{ paddingLeft: `${depth * 1.25}rem` }}
            >
                {hasChildren ? (
                    <button
                        onClick={() => toggle(node.id)}
                        aria-expanded={isExpanded}
                        aria-label={isExpanded ? "Свернуть" : "Развернуть"}
                        className="shrink-0 rounded p-0.5 text-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    >
                        {isExpanded ? "▾" : "▸"}
                    </button>
                ) : (
                    <span className="w-4 shrink-0" aria-hidden="true" />
                )}

                <span className="shrink-0 font-mono text-xs text-muted">{node.code}</span>
                <span
                    className={cn(
                        "flex-1 truncate text-foreground",
                        isPhase && "text-base font-bold",
                        isSection && "text-sm font-semibold",
                        !isPhase && !isSection && "text-sm"
                    )}
                >
                    {node.phase_name ?? node.title}
                </span>

                {node.role && <RoleBadge role={node.role} />}
                {node.progress && <ProgressBar done={node.progress.done} total={node.progress.total} />}

                {isLeaf && node.task && (
                    <button
                        onClick={() => navigate(`/kanban?highlight=${node.task!.id}`)}
                        className="shrink-0 rounded px-2 py-0.5 text-[11px] font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        style={{ color: stageColor, backgroundColor: `${stageColor}1A` }}
                    >
                        {node.task.stage_name}
                    </button>
                )}

                {isLeaf && node.task?.due_date && (
                    <span className="shrink-0 text-xs text-muted">
                        {new Date(node.task.due_date).toLocaleDateString("ru-RU")}
                    </span>
                )}

                <div className="flex shrink-0 gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                        onClick={() => setIsAddingChild((value) => !value)}
                        aria-label="Добавить подзадачу"
                        title="Добавить подзадачу"
                        className="rounded p-1 text-muted hover:bg-white/10 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    >
                        +
                    </button>
                    <button
                        onClick={() => setIsEditing((value) => !value)}
                        aria-label="Редактировать"
                        title="Редактировать"
                        className="rounded p-1 text-muted hover:bg-white/10 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    >
                        ✎
                    </button>
                    <button
                        onClick={handleDelete}
                        aria-label="Удалить"
                        title="Удалить"
                        className="rounded p-1 text-muted hover:bg-red-400/10 hover:text-red-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    >
                        ✕
                    </button>
                </div>
            </div>

            {mutationError && (
                <div style={{ paddingLeft: `${(depth + 1) * 1.25}rem` }} className="pb-2">
                    <ErrorMessage message={(mutationError as Error).message} />
                </div>
            )}

            {isEditing && (
                <div style={{ paddingLeft: `${(depth + 1) * 1.25}rem` }} className="pb-2">
                    <ItemForm
                        initialTitle={node.title}
                        initialRole={node.role}
                        submitLabel="Сохранить"
                        isPending={updateMutation.isPending}
                        onSubmit={(title, role) => updateMutation.mutate({ title, role })}
                        onCancel={() => setIsEditing(false)}
                    />
                </div>
            )}

            {isAddingChild && (
                <div style={{ paddingLeft: `${(depth + 1) * 1.25}rem` }} className="pb-2">
                    <ItemForm
                        initialTitle=""
                        initialRole={null}
                        submitLabel="Добавить"
                        isPending={createMutation.isPending}
                        onSubmit={(title, role) => createMutation.mutate({ title, role })}
                        onCancel={() => setIsAddingChild(false)}
                    />
                </div>
            )}

            {hasChildren && isExpanded && (
                <ul>
                    {node.children.map((child) => (
                        <WbsNode key={child.id} node={child} depth={depth + 1} />
                    ))}
                </ul>
            )}
        </li>
    );
}
