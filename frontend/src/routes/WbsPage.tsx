import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
    KanbanStage,
    KanbanTask,
    WbsItem,
    WbsNode as WbsNodeType,
    WbsRole,
} from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { ItemForm, WbsNode } from "@/components/wbs/WbsNode";
import { WbsMap } from "@/components/wbs/WbsMap";
import { TaskModal } from "@/components/kanban/TaskModal";
import { useUiStore } from "@/stores/ui";

const WBS_TREE_SKELETON_ROWS = [
    { depth: 0, width: "w-56" },
    { depth: 1, width: "w-48" },
    { depth: 2, width: "w-40" },
    { depth: 2, width: "w-36" },
    { depth: 1, width: "w-44" },
    { depth: 2, width: "w-40" },
    { depth: 0, width: "w-52" },
    { depth: 1, width: "w-40" },
];

function WbsTreeSkeleton() {
    return (
        <ul
            role="status"
            aria-live="polite"
            aria-label="Загрузка ИСР..."
            className="rounded-lg border border-white/20 bg-surface p-2"
        >
            {WBS_TREE_SKELETON_ROWS.map((row, index) => (
                <li
                    key={index}
                    className="flex items-center gap-2 rounded px-2 py-2"
                    style={{ paddingLeft: `${row.depth * 1.25 + 0.5}rem` }}
                >
                    <Skeleton className="h-3 w-3 shrink-0 rounded-sm" />
                    <Skeleton className={`h-4 ${row.width}`} />
                </li>
            ))}
        </ul>
    );
}

function WbsMapSkeleton() {
    return (
        <div
            role="status"
            aria-live="polite"
            aria-label="Загрузка карты ИСР..."
            className="overflow-hidden rounded-2xl border border-white/[0.08] bg-surface"
        >
            <div className="space-y-3 border-b border-white/[0.06] bg-surface-elevated/80 p-4">
                <Skeleton className="h-3 w-32" />
                <Skeleton className="h-7 w-24" />
            </div>
            <Skeleton className="h-[68dvh] min-h-[560px] max-h-[880px] w-full rounded-none" />
        </div>
    );
}

export function WbsPage() {
    const queryClient = useQueryClient();
    const [searchParams, setSearchParams] = useSearchParams();
    const view = searchParams.get("view") === "tree" ? "tree" : "map";
    const [isAddingPhase, setIsAddingPhase] = useState(false);
    const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);

    const treeQuery = useQuery({
        queryKey: ["wbs", "tree"],
        queryFn: () => api.get<WbsNodeType[]>("/api/v1/wbs/tree"),
    });
    const stagesQuery = useQuery({
        queryKey: ["kanban", "stages"],
        queryFn: () => api.get<KanbanStage[]>("/api/v1/kanban/stages"),
    });
    const selectedTaskQuery = useQuery({
        queryKey: ["kanban", "tasks", "detail", selectedTaskId],
        queryFn: () => api.get<KanbanTask>(`/api/v1/kanban/tasks/${selectedTaskId}`),
        enabled: selectedTaskId !== null,
    });

    const toggleWbsNode = useUiStore((state) => state.toggleWbsNode);
    const expandedOnce = useRef(false);

    useEffect(() => {
        if (treeQuery.data && !expandedOnce.current) {
            expandedOnce.current = true;
            treeQuery.data.forEach((root) => toggleWbsNode(root.id));
        }
    }, [treeQuery.data, toggleWbsNode]);

    const createPhaseMutation = useMutation({
        mutationFn: (vars: { title: string; role: WbsRole | null }) =>
            api.post<WbsItem>("/api/v1/wbs/items", {
                parent_id: null,
                title: vars.title,
                role: vars.role,
                phase_name: vars.title,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["wbs", "tree"] });
            queryClient.invalidateQueries({ queryKey: ["kanban", "tasks"] });
            setIsAddingPhase(false);
        },
    });

    const setView = (nextView: "map" | "tree") => {
        setSearchParams((current) => {
            const next = new URLSearchParams(current);
            if (nextView === "map") next.delete("view");
            else next.set("view", "tree");
            return next;
        });
        setIsAddingPhase(false);
    };

    const isPending = treeQuery.isPending || (view === "map" && stagesQuery.isPending);
    const error = treeQuery.error ?? (view === "map" ? stagesQuery.error : null);

    return (
        <div className="mx-auto min-w-0 max-w-[1600px]">
            <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <FocusHeading className="text-2xl font-bold">ИСР проекта</FocusHeading>
                    <p className="mt-1 max-w-2xl text-sm text-muted">
                        Структура работ, прогресс и актуальные стадии задач в одном представлении.
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <div
                        className="inline-flex rounded-lg border border-white/10 bg-surface p-1"
                        role="group"
                        aria-label="Режим отображения ИСР"
                    >
                        <button
                            type="button"
                            onClick={() => setView("map")}
                            aria-pressed={view === "map"}
                            className={`rounded-md px-3 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                                view === "map"
                                    ? "bg-surface-active text-foreground shadow-[var(--shadow-card)]"
                                    : "text-muted hover:text-foreground"
                            }`}
                        >
                            Карта
                        </button>
                        <button
                            type="button"
                            onClick={() => setView("tree")}
                            aria-pressed={view === "tree"}
                            className={`rounded-md px-3 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                                view === "tree"
                                    ? "bg-surface-active text-foreground shadow-[var(--shadow-card)]"
                                    : "text-muted hover:text-foreground"
                            }`}
                        >
                            Дерево
                        </button>
                    </div>
                    {view === "tree" && !isAddingPhase && (
                    <Button variant="secondary" onClick={() => setIsAddingPhase(true)}>
                        + Новая фаза
                    </Button>
                    )}
                </div>
            </div>

            {view === "tree" && isAddingPhase && (
                <div className="mb-4">
                    <ItemForm
                        initialTitle=""
                        initialRole={null}
                        submitLabel="Добавить фазу"
                        isPending={createPhaseMutation.isPending}
                        onSubmit={(title, role) => createPhaseMutation.mutate({ title, role })}
                        onCancel={() => setIsAddingPhase(false)}
                    />
                    {createPhaseMutation.isError && (
                        <div className="mt-2">
                            <ErrorMessage message={(createPhaseMutation.error as Error).message} />
                        </div>
                    )}
                </div>
            )}

            {isPending && (view === "tree" ? <WbsTreeSkeleton /> : <WbsMapSkeleton />)}
            {error && <ErrorMessage message={(error as Error).message} />}
            {treeQuery.data && treeQuery.data.length === 0 && <EmptyState message="Дерево ИСР пусто." />}
            {view === "map" && treeQuery.data && treeQuery.data.length > 0 && stagesQuery.data && (
                <WbsMap
                    tree={treeQuery.data}
                    stages={stagesQuery.data}
                    onOpenTask={setSelectedTaskId}
                />
            )}
            {view === "tree" && treeQuery.data && treeQuery.data.length > 0 && (
                <ul className="rounded-lg border border-white/20 bg-surface p-2">
                    {treeQuery.data.map((node) => (
                        <WbsNode key={node.id} node={node} depth={0} />
                    ))}
                </ul>
            )}

            {selectedTaskQuery.isError && (
                <div className="mt-4">
                    <ErrorMessage message={(selectedTaskQuery.error as Error).message} />
                </div>
            )}
            {selectedTaskQuery.data && (
                <TaskModal task={selectedTaskQuery.data} onClose={() => setSelectedTaskId(null)} />
            )}
        </div>
    );
}
