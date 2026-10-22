import { useRef, useState } from "react";
import { ProjectForm } from "@/components/projects/ProjectForm";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { formatDateOnly } from "@/lib/dates";
import { EMPTY_PROJECT_FORM, isProjectFormValid, toProjectPayload, type ProjectFormValues } from "@/lib/projectForm";
import type { ProjectCreate } from "@/lib/types";

interface BoardProjectDialogProps {
    boardTitle: string;
    onCreate: (project: ProjectCreate) => Promise<void>;
    onClose: () => void;
}

/** Mount with key=board.id only after parent flushes pending scene/metadata saves. */
export function BoardProjectDialog({ boardTitle, onCreate, onClose }: BoardProjectDialogProps) {
    const [values, setValues] = useState<ProjectFormValues>(() => ({
        ...EMPTY_PROJECT_FORM, name: boardTitle, start_date: formatDateOnly(new Date()),
        description_sections: { ...EMPTY_PROJECT_FORM.description_sections },
    }));
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const submitting = useRef(false);
    const close = () => { if (!submitting.current) onClose(); };
    const valid = isProjectFormValid(values) && Boolean(values.start_date) && values.name.trim().length <= 255;
    async function submit() {
        if (!valid || submitting.current) return;
        submitting.current = true; setPending(true); setError(null);
        try {
            await onCreate(toProjectPayload(values));
            onClose();
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Не удалось создать проект. Повторите действие.");
        } finally {
            submitting.current = false; setPending(false);
        }
    }
    return <Modal title="Создать проект из доски" isOpen size="md" isDismissable={!pending}
        onOpenChange={(open) => { if (!open) close(); }}
        footer={<>
            <Button disabled={pending} onClick={close}>Отмена</Button>
            <Button variant="primary" disabled={!valid || pending} onClick={() => void submit()}>
                {pending ? "Создаём проект…" : "Создать проект"}
            </Button>
        </>}>
        <p className="board-hint">Вы станете владельцем нового проекта. Эта доска перейдёт в проект вместе со всеми объектами.
            Команду и стадии можно настроить после создания.</p>
        {error && <p role="alert">{error}</p>}
        <ProjectForm values={values} onChange={setValues} disabled={pending} />
    </Modal>;
}
