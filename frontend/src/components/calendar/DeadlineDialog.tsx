import { useState } from "react";
import { CalendarClock } from "lucide-react";
import type { CalendarTask } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";

interface DeadlineDialogProps {
    task: CalendarTask;
    isSaving: boolean;
    onClose: () => void;
    onSave: (startDate: string | null, dueDate: string | null) => void;
    onFixBaseline?: () => void;
}

/** Доступная клавиатурная альтернатива переносу задачи мышью. */
export function DeadlineDialog({
    task,
    isSaving,
    onClose,
    onSave,
    onFixBaseline,
}: DeadlineDialogProps) {
    const [startDate, setStartDate] = useState(task.start_date ?? "");
    const [dueDate, setDueDate] = useState(task.due_date ?? "");
    const isReverse = startDate !== "" && dueDate !== "" && startDate > dueDate;
    const isUnchanged =
        startDate === (task.start_date ?? "") && dueDate === (task.due_date ?? "");

    return (
        <Modal
            isOpen
            onOpenChange={(open) => !open && onClose()}
            title={`Срок ${task.key}`}
            description={task.title}
            footer={
                <>
                    {onFixBaseline && (
                        <Button
                            variant="secondary"
                            disabled={isSaving}
                            onClick={onFixBaseline}
                            title="Текущие даты станут утверждённым слоем сравнения"
                        >
                            Зафиксировать baseline
                        </Button>
                    )}
                    <Button variant="ghost" onClick={onClose} disabled={isSaving}>
                        Отмена
                    </Button>
                    <Button
                        variant="primary"
                        icon={<CalendarClock size={14} />}
                        disabled={isSaving || isUnchanged || isReverse}
                        onClick={() => onSave(startDate || null, dueDate || null)}
                    >
                        {isSaving ? "Сохранение…" : "Сохранить"}
                    </Button>
                </>
            }
        >
            <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Начало">
                    {(id) => (
                        <Input
                            id={id}
                            type="date"
                            value={startDate}
                            max={dueDate || undefined}
                            autoFocus
                            onChange={(event) => setStartDate(event.target.value)}
                        />
                    )}
                </Field>
                <Field
                    label="Завершение"
                    hint="Очистите поле, чтобы вернуть задачу в список без срока."
                    error={isReverse ? "Завершение не может быть раньше начала." : undefined}
                >
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
            {(task.baseline_start_date || task.baseline_due_date) && (
                <p className="mt-3 text-[11px] text-muted">
                    Текущий baseline: {task.baseline_start_date ?? "—"} —{" "}
                    {task.baseline_due_date ?? "—"}
                </p>
            )}
        </Modal>
    );
}
