import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, endpoints, queryKeys } from "@/lib/api";
import type {
    ProjectSticker,
    ProjectStickerCreateInput,
    ProjectStickerInput,
    ProjectStickerPositionInput,
    ProjectStickerUpdateInput,
} from "@/lib/board/stickers";
import type { ProjectMember, Task } from "@/lib/types";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { ProjectStickerBoard } from "@/components/board/ProjectStickerBoard";
import { Button } from "@/components/ui/Button";
import { ErrorMessage, Skeleton } from "@/components/ui/States";

function ProjectBoardSkeleton() {
    return (
        <div role="status" aria-label="Загрузка доски" className="p-4 sm:p-5">
            <div className="mb-5 flex items-center justify-between gap-4">
                <Skeleton className="h-10 w-56" />
                <Skeleton className="h-8 w-36" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                {Array.from({ length: 6 }, (_, index) => (
                    <Skeleton key={index} className="h-56" />
                ))}
            </div>
        </div>
    );
}

export function ProjectBoardPage() {
    const project = useProjectOutlet();
    const queryClient = useQueryClient();
    const stickersKey = queryKeys.projectStickers(project.id);

    const stickersQuery = useQuery({
        queryKey: stickersKey,
        queryFn: () => api.get<ProjectSticker[]>(endpoints.projectStickers(project.id)),
        retry: 1,
    });
    const membersQuery = useQuery({
        queryKey: queryKeys.projectMembers(project.id),
        queryFn: () => api.get<ProjectMember[]>(endpoints.projectMembers(project.id)),
        retry: 1,
    });
    const tasksQuery = useQuery({
        queryKey: queryKeys.tasks(project.id),
        queryFn: () => api.get<Task[]>(endpoints.projectTasks(project.id)),
        retry: 1,
    });

    function refreshAfterConflict(error: unknown) {
        if (error instanceof ApiError && error.status === 409) {
            void queryClient.invalidateQueries({ queryKey: stickersKey });
        }
    }

    const createMutation = useMutation({
        mutationFn: (input: ProjectStickerCreateInput) =>
            api.post<ProjectSticker>(endpoints.projectStickers(project.id), input),
        onSuccess: (created) => {
            queryClient.setQueryData<ProjectSticker[]>(stickersKey, (current = []) => [
                created,
                ...current,
            ]);
        },
    });
    const updateMutation = useMutation({
        mutationFn: ({ sticker, input }: { sticker: ProjectSticker; input: ProjectStickerInput }) => {
            const latest = queryClient
                .getQueryData<ProjectSticker[]>(stickersKey)
                ?.find((item) => item.id === sticker.id);
            return api.patch<ProjectSticker>(endpoints.projectSticker(project.id, sticker.id), {
                ...input,
                revision: latest?.revision ?? sticker.revision,
            } satisfies ProjectStickerUpdateInput);
        },
        onSuccess: (updated) => {
            queryClient.setQueryData<ProjectSticker[]>(stickersKey, (current = []) =>
                current.map((sticker) => sticker.id === updated.id ? updated : sticker),
            );
        },
        onError: refreshAfterConflict,
    });
    const deleteMutation = useMutation({
        mutationFn: (sticker: ProjectSticker) => {
            const latest = queryClient
                .getQueryData<ProjectSticker[]>(stickersKey)
                ?.find((item) => item.id === sticker.id);
            return api.delete<void>(
                `${endpoints.projectSticker(project.id, sticker.id)}?revision=${latest?.revision ?? sticker.revision}`,
            );
        },
        onSuccess: (_, deleted) => {
            queryClient.setQueryData<ProjectSticker[]>(stickersKey, (current = []) =>
                current.filter((sticker) => sticker.id !== deleted.id),
            );
        },
        onError: refreshAfterConflict,
    });
    const moveMutation = useMutation({
        mutationFn: ({
            sticker,
            position,
        }: {
            sticker: ProjectSticker;
            position: ProjectStickerPositionInput;
        }) => api.patch<ProjectSticker>(
            endpoints.projectStickerPosition(project.id, sticker.id),
            position,
        ),
        onSuccess: (moved) => {
            queryClient.setQueryData<ProjectSticker[]>(stickersKey, (current = []) =>
                current.map((sticker) => sticker.id === moved.id
                    ? {
                        ...sticker,
                        canvas_x: moved.canvas_x,
                        canvas_y: moved.canvas_y,
                        width: moved.width,
                        height: moved.height,
                    }
                    : sticker,
                ),
            );
        },
        onError: (error) => {
            if (error instanceof ApiError && error.status === 404) {
                void queryClient.invalidateQueries({ queryKey: stickersKey });
            }
        },
    });

    if (stickersQuery.isPending || membersQuery.isPending) return <ProjectBoardSkeleton />;

    const loadingError = stickersQuery.error ?? membersQuery.error;
    if (loadingError || !stickersQuery.data || !membersQuery.data) {
        return (
            <div className="p-4 sm:p-5">
                <ErrorMessage
                    message={(loadingError as Error | null)?.message ?? "Сервер вернул пустой ответ."}
                    action={
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                                void stickersQuery.refetch();
                                void membersQuery.refetch();
                            }}
                        >
                            Повторить
                        </Button>
                    }
                />
            </div>
        );
    }

    return (
        <ProjectStickerBoard
            project={project}
            stickers={stickersQuery.data}
            members={membersQuery.data}
            tasks={tasksQuery.data ?? []}
            tasksLoading={tasksQuery.isPending}
            tasksError={(tasksQuery.error as Error | null) ?? null}
            isSaving={createMutation.isPending || updateMutation.isPending}
            isDeleting={deleteMutation.isPending}
            onRetryTasks={() => void tasksQuery.refetch()}
            onCreate={(input) => createMutation.mutateAsync(input)}
            onUpdate={(sticker, input) => updateMutation.mutateAsync({ sticker, input })}
            onMove={(sticker, position) => moveMutation.mutateAsync({ sticker, position })}
            onResize={(sticker, size) => moveMutation.mutateAsync({ sticker, position: { canvas_x: sticker.canvas_x, canvas_y: sticker.canvas_y, ...size } })}
            onDelete={(sticker) => deleteMutation.mutateAsync(sticker)}
        />
    );
}
