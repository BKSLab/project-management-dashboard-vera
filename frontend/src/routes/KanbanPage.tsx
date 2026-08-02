import { useDeferredValue, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { KanbanStage, KanbanTask } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Board } from "@/components/kanban/Board";
import { TaskModal } from "@/components/kanban/TaskModal";

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

            {isPending && <Spinner />}
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
