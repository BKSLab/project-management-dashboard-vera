import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { ProjectDeadlineChange } from "@/lib/types";
import { Section } from "@/components/ui/Card";
import { ErrorMessage, Skeleton } from "@/components/ui/States";

function dateLabel(value: string | null) {
    return value ? value.split("-").reverse().join(".") : "Без даты";
}

export function ProjectDeadlineHistory({ projectId }: { projectId: number }) {
    const query = useQuery({
        queryKey: queryKeys.projectDeadlineHistory(projectId),
        queryFn: () => api.get<ProjectDeadlineChange[]>(endpoints.projectDeadlineHistory(projectId)),
    });
    return (
        <Section title="История срока окончания">
            {query.isPending && <Skeleton className="h-16 w-full" />}
            {query.error && <ErrorMessage message={(query.error as Error).message} action={<Button onClick={() => query.refetch()}>Повторить</Button>} />}
            {query.data?.length === 0 && <p className="text-[13px] text-muted">Срок окончания ещё не назначался.</p>}
            <ol className="divide-y divide-line-subtle">
                {query.data?.map((change) => (
                    <li key={change.id} className="flex flex-col gap-1.5 py-3 text-[13px]">
                        <p className="font-medium text-secondary">{dateLabel(change.previous_due_date)} → {dateLabel(change.new_due_date)}</p>
                        {change.comment && <p className="whitespace-pre-wrap break-words text-primary">{change.comment}</p>}
                        <p className="text-[12px] text-muted">{change.changed_by_name} · <time dateTime={change.created_at}>{new Date(change.created_at).toLocaleString("ru-RU")}</time></p>
                    </li>
                ))}
            </ol>
        </Section>
    );
}
