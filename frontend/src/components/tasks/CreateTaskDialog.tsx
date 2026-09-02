import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { ProjectStage, Task, TaskPriority } from "@/lib/types";
import { PRIORITY_LABELS, PRIORITY_ORDER } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorMessage } from "@/components/ui/States";

interface CreateTaskDialogProps {
    projectId: number;
    stages: ProjectStage[];
    /** Раздел ИСР, если задача создаётся прямо в структуре. */
    wbsNodeId?: number | null;
    isOpen: boolean;
    onClose: () => void;
    onCreated?: (task: Task) => void;
}

export function CreateTaskDialog({
    projectId,
    stages,
    wbsNodeId = null,
    isOpen,
    onClose,
    onCreated,
}: CreateTaskDialogProps) {
    const queryClient = useQueryClient();
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [priority, setPriority] = useState<TaskPriority>("MEDIUM");
    const [stageId, setStageId] = useState<string>("");
    const [startDate, setStartDate] = useState("");
    const [dueDate, setDueDate] = useState("");

    function reset() {
        setTitle("");
        setDescription("");
        setPriority("MEDIUM");
        setStageId("");
        setStartDate("");
        setDueDate("");
    }

    const createMutation = useMutation({
        mutationFn: () =>
            api.post<Task>(endpoints.projectTasks(projectId), {
                title: title.trim(),
                description_md: description.trim() || null,
                priority,
                stage_id: stageId === "" ? null : Number(stageId),
                wbs_node_id: wbsNodeId,
                start_date: startDate || null,
                due_date: dueDate || null,
            }),
        onSuccess: (task) => {
            queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
            queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
            reset();
            onCreated?.(task);
            onClose();
        },
    });

    return (
        <Modal
            title="Новая задача"
            isOpen={isOpen}
            onOpenChange={(open) => {
                if (!open) {
                    onClose();
                }
            }}
            footer={
                <>
                    <Button onClick={onClose}>Отмена</Button>
                    <Button
                        variant="primary"
                        disabled={title.trim() === "" || createMutation.isPending}
                        onClick={() => createMutation.mutate()}
                    >
                        Создать
                    </Button>
                </>
            }
        >
            <div className="flex flex-col gap-3">
                {createMutation.error && (
                    <ErrorMessage
                        title="Не удалось создать задачу"
                        message={(createMutation.error as Error).message}
                    />
                )}

                <Field label="Название">
                    {(id) => (
                        <Input
                            id={id}
                            autoFocus
                            value={title}
                            placeholder="Что нужно сделать"
                            onChange={(event) => setTitle(event.target.value)}
                        />
                    )}
                </Field>

                <Field label="Описание" hint="Markdown поддерживается">
                    {(id) => (
                        <Textarea
                            id={id}
                            rows={4}
                            value={description}
                            onChange={(event) => setDescription(event.target.value)}
                        />
                    )}
                </Field>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <Field label="Стадия">
                        {(id) => (
                            <Select
                                id={id}
                                value={stageId}
                                onChange={(event) => setStageId(event.target.value)}
                            >
                                <option value="">Первая стадия</option>
                                {stages.map((stage) => (
                                    <option key={stage.id} value={stage.id}>
                                        {stage.name}
                                    </option>
                                ))}
                            </Select>
                        )}
                    </Field>

                    <Field label="Приоритет">
                        {(id) => (
                            <Select
                                id={id}
                                value={priority}
                                onChange={(event) =>
                                    setPriority(event.target.value as TaskPriority)
                                }
                            >
                                {PRIORITY_ORDER.map((item) => (
                                    <option key={item} value={item}>
                                        {PRIORITY_LABELS[item]}
                                    </option>
                                ))}
                            </Select>
                        )}
                    </Field>

                    <Field label="Начало">
                        {(id) => (
                            <Input
                                id={id}
                                type="date"
                                value={startDate}
                                max={dueDate || undefined}
                                onChange={(event) => setStartDate(event.target.value)}
                            />
                        )}
                    </Field>

                    <Field label="Завершение">
                        {(id) => (
                            <Input
                                id={id}
                                type="date"
                                value={dueDate}
                                min={startDate || undefined}
                                onChange={(event) => setDueDate(event.target.value)}
                            />
                        )}
                    </Field>
                </div>
            </div>
        </Modal>
    );
}
