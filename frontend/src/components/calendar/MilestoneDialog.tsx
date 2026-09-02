import { useState } from "react";
import { Diamond } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import type {
    CalendarWbsNode,
    ProjectMilestone,
    ProjectMilestoneInput,
    ProjectMilestoneStatus,
} from "@/lib/types";

interface MilestoneDialogProps {
    milestone: ProjectMilestone | null;
    initialDueDate: string;
    wbsNodes: CalendarWbsNode[];
    isSaving: boolean;
    onClose: () => void;
    onSave: (data: ProjectMilestoneInput) => void;
}

/** Форма отдельной проектной вехи без собственного workflow. */
export function MilestoneDialog({
    milestone,
    initialDueDate,
    wbsNodes,
    isSaving,
    onClose,
    onSave,
}: MilestoneDialogProps) {
    const [title, setTitle] = useState(milestone?.title ?? "");
    const [dueDate, setDueDate] = useState(milestone?.due_date ?? initialDueDate);
    const [status, setStatus] = useState<ProjectMilestoneStatus>(
        milestone?.status ?? "PLANNED",
    );
    const [wbsNodeId, setWbsNodeId] = useState(
        milestone?.wbs_node_id ? String(milestone.wbs_node_id) : "",
    );
    const [description, setDescription] = useState(milestone?.description_md ?? "");
    const normalizedTitle = title.trim();

    return (
        <Modal
            isOpen
            onOpenChange={(open) => !open && onClose()}
            title={milestone ? "Изменить веху" : "Новая веха"}
            description="Контрольная точка проекта на временной карте"
            footer={
                <>
                    <Button variant="ghost" onClick={onClose} disabled={isSaving}>
                        Отмена
                    </Button>
                    <Button
                        variant="primary"
                        icon={<Diamond size={13} aria-hidden="true" />}
                        disabled={isSaving || normalizedTitle.length === 0 || dueDate === ""}
                        onClick={() =>
                            onSave({
                                title: normalizedTitle,
                                due_date: dueDate,
                                status,
                                wbs_node_id: wbsNodeId ? Number(wbsNodeId) : null,
                                description_md: description.trim() || null,
                            })
                        }
                    >
                        {isSaving ? "Сохранение…" : "Сохранить"}
                    </Button>
                </>
            }
        >
            <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Название" className="sm:col-span-2">
                    {(id) => (
                        <Input
                            id={id}
                            value={title}
                            maxLength={255}
                            autoFocus
                            onChange={(event) => setTitle(event.target.value)}
                        />
                    )}
                </Field>
                <Field label="Дата">
                    {(id) => (
                        <Input
                            id={id}
                            type="date"
                            value={dueDate}
                            onChange={(event) => setDueDate(event.target.value)}
                        />
                    )}
                </Field>
                <Field label="Статус">
                    {(id) => (
                        <Select
                            id={id}
                            value={status}
                            onChange={(event) =>
                                setStatus(event.target.value as ProjectMilestoneStatus)
                            }
                        >
                            <option value="PLANNED">Запланирована</option>
                            <option value="ACHIEVED">Достигнута</option>
                        </Select>
                    )}
                </Field>
                <Field label="Раздел ИСР" className="sm:col-span-2">
                    {(id) => (
                        <Select
                            id={id}
                            value={wbsNodeId}
                            onChange={(event) => setWbsNodeId(event.target.value)}
                        >
                            <option value="">Весь проект</option>
                            {wbsNodes.map((node) => (
                                <option key={node.id} value={node.id}>
                                    {node.title}
                                </option>
                            ))}
                        </Select>
                    )}
                </Field>
                <Field label="Описание" className="sm:col-span-2">
                    {(id) => (
                        <Textarea
                            id={id}
                            rows={5}
                            value={description}
                            onChange={(event) => setDescription(event.target.value)}
                        />
                    )}
                </Field>
            </div>
        </Modal>
    );
}
