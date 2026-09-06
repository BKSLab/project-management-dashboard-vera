import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, endpoints, queryKeys } from "@/lib/api";
import { checklistInput, isChecklistValid } from "@/lib/checklists";
import type { TaskChecklist } from "@/lib/checklists";
import type { Task } from "@/lib/types";
import { TaskChecklistField } from "@/components/tasks/TaskChecklistField";
import { Button } from "@/components/ui/Button";
import { ErrorMessage } from "@/components/ui/States";

export function TaskChecklistSection({ task, description }: { task: Task; description: string }) {
    const queryClient = useQueryClient();
    const [draft, setDraft] = useState<{ value: TaskChecklist | null; revision: number } | null>(null);
    const [pendingValue, setPendingValue] = useState<{ value: TaskChecklist | null } | null>(null);
    const [aiBusy, setAiBusy] = useState(false);
    const [fieldKey, setFieldKey] = useState(0);
    const save = useMutation({
        mutationFn: ({ value, revision }: { value: TaskChecklist | null; revision: number }) =>
            api.patch<Task>(endpoints.task(task.id), { checklist: checklistInput(value), checklist_revision: revision }),
        onSuccess: updated => {
            queryClient.setQueryData(queryKeys.task(task.id), updated);
            setDraft(null);
            queryClient.invalidateQueries({ queryKey: ["projects", task.project_id] });
            queryClient.invalidateQueries({ queryKey: queryKeys.taskActivity(task.id) });
            queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
        },
        onSettled: () => setPendingValue(null),
    });
    const revision = draft?.revision ?? task.checklist_revision ?? 0;
    const value = draft ? draft.value : pendingValue ? pendingValue.value : task.checklist ?? null;
    function change(next: TaskChecklist | null) {
        if (draft || !task.checklist) setDraft({ value: next, revision });
        else {
            setPendingValue({ value: next });
            save.mutate({ value: next, revision });
        }
    }
    return <div className="flex flex-col gap-2">
        <TaskChecklistField key={fieldKey} projectId={task.project_id} taskId={task.id} title={task.title} description={description}
            value={value} onChange={change} editing={draft !== null} disabled={save.isPending}
            revision={revision} onBusyChange={setAiBusy}
            onEdit={() => setDraft({ value: structuredClone(task.checklist ?? null), revision })}
            onAccept={async (checklist, sourceRevision) => { await save.mutateAsync({ value: checklist, revision: sourceRevision ?? revision }); }}
            onRemove={async () => {
                if (task.checklist) await save.mutateAsync({ value: null, revision });
                else setDraft(null);
            }} />
        {save.error && <ErrorMessage message={(save.error as Error).message} />}
        {save.error instanceof ApiError && save.error.status === 409 && <Button size="sm" onClick={async () => {
            await queryClient.invalidateQueries({ queryKey: queryKeys.task(task.id) });
            setDraft(null);
            setFieldKey(key => key + 1);
            save.reset();
        }}>Загрузить актуальный чек-лист</Button>}
        {draft && <div className="flex justify-end gap-2">
            <Button size="sm" disabled={save.isPending || aiBusy} onClick={() => { setDraft(null); save.reset(); }}>Отменить правки</Button>
            <Button size="sm" variant="primary" disabled={save.isPending || aiBusy || !isChecklistValid(value)}
                onClick={() => save.mutate({ value, revision })}>{save.isPending ? "Сохранение…" : "Сохранить чек-лист"}</Button>
        </div>}
    </div>;
}
