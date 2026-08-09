import { useDeferredValue, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { KanbanStage, KanbanTask } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Board } from "@/components/kanban/Board";
import { TaskModal } from "@/components/kanban/TaskModal";

const BOARD_SKELETON_COLUMNS = [3, 4, 2, 3, 5];

function BoardSkeleton() {
    return (
        <div
            role="status"
            aria-live="polite"
            aria-label="Загрузка канбана..."
            className="scrollbar-thin overflow-x-auto pb-4"
        >
            <div className="flex w-max min-w-full justify-start gap-4">
                {BOARD_SKELETON_COLUMNS.map((cardCount, columnIndex) => (
                    <div
                        key={columnIndex}
                        className="flex h-[75vh] w-[calc(100vw-2rem)] shrink-0 flex-col rounded-2xl border border-white/[0.05] bg-surface sm:w-80"
                    >
                        <div className="flex items-center justify-between gap-2 border-b-2 border-white/10 px-4 py-3">
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-3 w-10" />
                        </div>
                        <div className="flex flex-1 flex-col gap-3 p-4">
                            {Array.from({ length: cardCount }).map((_, cardIndex) => (
                                <div
                                    key={cardIndex}
                                    className="space-y-2 rounded-xl border border-white/[0.05] bg-surface-elevated p-3"
                                >
                                    <Skeleton className="h-3 w-16" />
                                    <Skeleton className="h-4 w-4/5" />
                                    <Skeleton className="h-3 w-full" />
                                    <Skeleton className="h-3 w-2/3" />
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export function KanbanPage() {
    const [searchParams] = useSearchParams();
    const highlightParam = searchParams.get("highlight");
    const highlightedTaskId = highlightParam ? Number(highlightParam) : null;

    const [selectedTaskId, setSelectedTaskId] = useState<number | null>(() => highlightedTaskId);
    const [search, setSearch] = useState("");
    const deferredSearch = useDeferredValue(search.trim());

    const stagesQuery = useQuery({
        queryKey: ["kanban", "stages"],
        queryFn: () => api.get<KanbanStage[]>("/api/v1/kanban/stages"),
    });

    const tasksQuery = useQuery({
        queryKey: deferredSearch
            ? ["kanban", "tasks", "search", deferredSearch]
            : ["kanban", "tasks"],
        queryFn: () =>
            api.get<KanbanTask[]>(
                deferredSearch
                    ? `/api/v1/kanban/tasks?search=${encodeURIComponent(deferredSearch)}`
                    : "/api/v1/kanban/tasks"
            ),
    });

    const selectedTaskQuery = useQuery({
        queryKey: ["kanban", "tasks", "detail", selectedTaskId],
        queryFn: () => api.get<KanbanTask>(`/api/v1/kanban/tasks/${selectedTaskId}`),
        enabled: selectedTaskId !== null,
    });

    const isPending = stagesQuery.isPending || tasksQuery.isPending;
    const error = stagesQuery.error ?? tasksQuery.error;

    const selectedTask = selectedTaskQuery.data
        ?? tasksQuery.data?.find((task) => task.id === selectedTaskId);

    return (
        <div>
            <div className="relative mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-center">
                <FocusHeading className="text-2xl font-bold">Канбан</FocusHeading>
                <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Название, описание, комментарий или код ИСР..."
                    aria-label="Поиск задач"
                    className="w-full rounded border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:absolute sm:right-0 sm:max-w-xs"
                />
            </div>

            {isPending && <BoardSkeleton />}
            {error && <ErrorMessage message={(error as Error).message} />}

            {stagesQuery.data && tasksQuery.data && (
                <Board
                    stages={stagesQuery.data}
                    tasks={tasksQuery.data}
                    highlightedTaskId={highlightedTaskId}
                    onTaskClick={setSelectedTaskId}
                />
            )}

            {selectedTask && <TaskModal task={selectedTask} onClose={() => setSelectedTaskId(null)} />}
        </div>
    );
}
