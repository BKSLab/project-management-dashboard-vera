import { useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ListTodo, Plus, Search } from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { ProjectStage, Task } from "@/lib/types";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { useUiStore } from "@/stores/ui";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { EmptyState, ErrorMessage, Skeleton } from "@/components/ui/States";
import { Board } from "@/components/kanban/Board";
import { CreateTaskDialog } from "@/components/tasks/CreateTaskDialog";

function BoardSkeleton() {
    return (
        <div role="status" aria-label="Загрузка доски" className="flex gap-3 px-5 py-4">
            {[3, 4, 2, 3].map((cards, columnIndex) => (
                <div key={columnIndex} className="flex w-[300px] shrink-0 flex-col gap-2">
                    <Skeleton className="h-4 w-28" />
                    {Array.from({ length: cards }).map((_, cardIndex) => (
                        <Skeleton key={cardIndex} className="h-24 w-full" />
                    ))}
                </div>
            ))}
        </div>
    );
}

export function BoardPage() {
    const project = useProjectOutlet();
    const selectedTaskId = useUiStore((state) => state.selectedTaskId);
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);
    const [search, setSearch] = useState("");
    const [isCreateOpen, setCreateOpen] = useState(false);
    const deferredSearch = useDeferredValue(search.trim());

    const stagesQuery = useQuery({
        queryKey: queryKeys.stages(project.id),
        queryFn: () => api.get<ProjectStage[]>(endpoints.projectStages(project.id)),
    });

    const tasksQuery = useQuery({
        queryKey: queryKeys.tasks(project.id, deferredSearch),
        queryFn: () =>
            api.get<Task[]>(
                deferredSearch
                    ? `${endpoints.projectTasks(project.id)}?search=${encodeURIComponent(deferredSearch)}`
                    : endpoints.projectTasks(project.id),
            ),
    });

    const error = stagesQuery.error ?? tasksQuery.error;
    const hasTasks = (tasksQuery.data?.length ?? 0) > 0;

    return (
        <div className="flex h-full min-w-0 flex-col">
            <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-line px-5 py-2.5">
                <div className="relative min-w-0 flex-1 sm:max-w-xs">
                    <Search
                        size={14}
                        aria-hidden="true"
                        className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-disabled"
                    />
                    <Input
                        value={search}
                        aria-label="Поиск задач проекта"
                        placeholder="Название, описание, комментарий, номер"
                        className="pl-8"
                        onChange={(event) => setSearch(event.target.value)}
                    />
                </div>
                <Button variant="primary" icon={<Plus size={15} />} onClick={() => setCreateOpen(true)}>
                    Задача
                </Button>
            </div>

            {error && (
                <div className="p-5">
                    <ErrorMessage message={(error as Error).message} />
                </div>
            )}

            {(stagesQuery.isPending || tasksQuery.isPending) && <BoardSkeleton />}

            {stagesQuery.data && tasksQuery.data && !hasTasks && (
                <div className="p-5">
                    <EmptyState
                        title={
                            deferredSearch
                                ? "Ничего не найдено"
                                : "В проекте пока нет задач"
                        }
                        description={
                            deferredSearch
                                ? "Измените запрос или очистите поиск."
                                : "Создайте первую задачу, чтобы начать работу."
                        }
                        icon={<ListTodo size={24} />}
                        action={
                            deferredSearch ? undefined : (
                                <Button
                                    variant="primary"
                                    icon={<Plus size={15} />}
                                    onClick={() => setCreateOpen(true)}
                                >
                                    Создать задачу
                                </Button>
                            )
                        }
                    />
                </div>
            )}

            {stagesQuery.data && tasksQuery.data && hasTasks && (
                <div className="min-h-0 flex-1">
                    <Board
                        projectId={project.id}
                        stages={stagesQuery.data}
                        tasks={tasksQuery.data}
                        search={deferredSearch}
                        selectedTaskId={selectedTaskId}
                        onTaskOpen={setSelectedTaskId}
                    />
                </div>
            )}

            <CreateTaskDialog
                projectId={project.id}
                stages={stagesQuery.data ?? []}
                isOpen={isCreateOpen}
                onClose={() => setCreateOpen(false)}
                onCreated={(task) => setSelectedTaskId(task.id)}
            />
        </div>
    );
}
