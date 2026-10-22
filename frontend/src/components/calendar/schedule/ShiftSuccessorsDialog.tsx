import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { plural } from "@/lib/plural";
import type { ScenarioPreview } from "@/lib/types";

interface ShiftSuccessorsDialogProps {
    taskKey: string;
    preview: ScenarioPreview;
    isApplying: boolean;
    onShiftAll: () => void;
    onOnlyThis: () => void;
    onCancel: () => void;
}

/** Вопрос после переноса полосы: сдвинуть и зависящие задачи или только эту. */
export function ShiftSuccessorsDialog({
    taskKey,
    preview,
    isApplying,
    onShiftAll,
    onOnlyThis,
    onCancel,
}: ShiftSuccessorsDialogProps) {
    const count = preview.consequences_count;
    const cascaded = preview.changes.filter((change) => change.source === "CASCADE");
    return (
        <Modal
            isOpen
            title={`Сдвинуть и ${count} ${plural(count, "следующую", "следующие", "следующих")}?`}
            description={`После переноса ${taskKey} зависящие от неё задачи начнутся раньше, чем она закончится.`}
            onOpenChange={(open) => !open && onCancel()}
            footer={
                <>
                    <Button variant="ghost" onClick={onCancel} disabled={isApplying} title="Ничего не менять">
                        Отмена
                    </Button>
                    <Button
                        onClick={onOnlyThis}
                        disabled={isApplying}
                        title="Перенести только эту задачу — зависящие останутся на месте, конфликт будет виден как риск"
                    >
                        Только эту
                    </Button>
                    <Button
                        variant="primary"
                        onClick={onShiftAll}
                        disabled={isApplying || !preview.can_apply}
                        title="Перенести эту задачу и сдвинуть все зависящие от неё задачи так, чтобы связи не нарушались"
                    >
                        Да, сдвинуть
                    </Button>
                </>
            }
        >
            <ul className="flex max-h-60 flex-col gap-1 overflow-auto text-[12px]" aria-label="Задачи, которые сдвинутся">
                {cascaded.map((change) => (
                    <li key={change.task_id} className="flex justify-between gap-3">
                        <span className="min-w-0 truncate">
                            <span className="font-mono text-[11px] text-accent">{change.task_key}</span> {change.task_title}
                        </span>
                        <span className="shrink-0 font-mono text-[11px] text-muted">
                            {change.current.due_date ?? "—"} → {change.proposed.due_date ?? "—"}
                        </span>
                    </li>
                ))}
            </ul>
            {preview.conflicts.length > 0 && (
                <p role="alert" className="mt-2 text-[12px] text-danger">
                    {preview.conflicts[0].message}
                </p>
            )}
        </Modal>
    );
}
