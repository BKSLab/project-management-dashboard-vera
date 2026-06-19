import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { KanbanStage, KanbanTask } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Board } from "@/components/kanban/Board";
import { TaskDrawer } from "@/components/kanban/TaskDrawer";

export function KanbanPage() {
    const [searchParams] = useSearchParams();
    const highlightParam = searchParams.get("highlight");
    const highlightedTaskId = highlightParam ? Number(highlightParam) : null;

    const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
    const [search, setSearch] = useState("");

    useEffect(() => {
        if (highlightedTaskId !== null) {
            setSelectedTaskId(highlightedTaskId);
        }
    }, [highlightedTaskId]);

    const stagesQuery = useQuery({
        queryKey: ["kanban", "stages"],
        queryFn: () => api.get<KanbanStage[]>("/api/kanban/stages"),
    });

    const tasksQuery = useQuery({
        queryKey: ["kanban", "tasks"],
        queryFn: () => api.get<KanbanTask[]>("/api/kanban/tasks"),
    });

    const isPending = stagesQuery.isPending || tasksQuery.isPending;
    const error = stagesQuery.error ?? tasksQuery.error;

    const filteredTasks = useMemo(() => {
        if (!tasksQuery.data) return undefined;
        const query = search.trim().toLowerCase();
        if (!query) return tasksQuery.data;
        return tasksQuery.data.filter(
            (task) =>
                task.title.toLowerCase().includes(query) ||
                task.wbs_code?.toLowerCase().includes(query)
        );
    }, [tasksQuery.data, search]);

    const selectedTask =
        selectedTaskId !== null ? tasksQuery.data?.find((task) => task.id === selectedTaskId) : undefined;

    return (
        <div>
            <div className="relative mb-6 flex items-center justify-center">
                <FocusHeading className="text-2xl font-bold">Канбан</FocusHeading>
                <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Поиск по названию или коду ИСР..."
                    className="absolute right-0 w-full max-w-xs rounded border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                />
            </div>

            {isPending && <Spinner />}
            {error && <ErrorMessage message={(error as Error).message} />}

            {stagesQuery.data && filteredTasks && (
                <Board
                    stages={stagesQuery.data}
                    tasks={filteredTasks}
                    highlightedTaskId={highlightedTaskId}
                    onTaskClick={setSelectedTaskId}
                />
            )}

            {selectedTask && <TaskDrawer task={selectedTask} onClose={() => setSelectedTaskId(null)} />}
        </div>
    );
}
