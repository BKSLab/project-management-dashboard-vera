import { useQuery } from "@tanstack/react-query";
import { Network } from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { WbsStructure } from "@/lib/types";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { StatTile } from "@/components/ui/Progress";
import { EmptyState, ErrorMessage, Skeleton } from "@/components/ui/States";

/**
 * Заглушка раздела «Структура». Интерактивный конструктор ИСР — отдельный
 * этап работ: canvas на React Flow, пул нераспределённых задач, auto-layout.
 * Пока экран показывает готовность данных, чтобы раздел не был пустым.
 */
export function StructurePage() {
    const project = useProjectOutlet();

    const wbsQuery = useQuery({
        queryKey: queryKeys.wbs(project.id),
        queryFn: () => api.get<WbsStructure>(endpoints.wbs(project.id)),
    });

    return (
        <div className="scrollbar-thin h-full overflow-y-auto">
            <div className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-5 py-5">
                {wbsQuery.error && <ErrorMessage message={(wbsQuery.error as Error).message} />}
                {wbsQuery.isPending && <Skeleton className="h-24 w-full" />}

                {wbsQuery.data && (
                    <>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                            <StatTile label="Разделов" value={wbsQuery.data.stats.total_nodes} />
                            <StatTile
                                label="Распределено"
                                value={wbsQuery.data.stats.assigned_tasks}
                            />
                            <StatTile
                                label="В пуле"
                                value={wbsQuery.data.stats.unassigned_tasks}
                                hint="Задачи вне структуры"
                            />
                            <StatTile
                                label="Выполнено"
                                value={wbsQuery.data.stats.done_tasks}
                                tone="success"
                            />
                        </div>

                        <EmptyState
                            title="Конструктор ИСР готовится"
                            description={
                                "Backend структуры уже работает: разделы, перенос с пересчётом позиций " +
                                "и распределение задач. Интерактивная карта появится следующим этапом."
                            }
                            icon={<Network size={24} />}
                        />
                    </>
                )}
            </div>
        </div>
    );
}
