import { useId } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, endpoints } from "@/lib/api";
import { riskInput, type ProjectRisk, type RiskInput } from "@/lib/risks";
import { useInvalidateRisks } from "@/lib/useRisks";
import { useToast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { RiskForm } from "@/components/risks/RiskForm";

interface Props {
    projectId: number;
    initial?: Partial<RiskInput>;
    onClose: () => void;
    onCreated?: (risk: ProjectRisk) => void;
}

export function CreateRiskDialog({ projectId, initial, onClose, onCreated }: Props) {
    const formId = useId();
    const invalidate = useInvalidateRisks(projectId);
    const toast = useToast();
    const create = useMutation({
        mutationFn: (input: RiskInput) => api.post<ProjectRisk>(endpoints.projectRisks(projectId), riskInput(input)),
        onSuccess: (risk) => {
            void invalidate();
            toast.success(`Риск ${risk.key} создан`);
            onCreated?.(risk);
            onClose();
        },
    });
    return (
        <Modal
            isOpen size="md" tall title="Новый риск"
            description={initial?.source === "AI_SUGGESTED" ? "Проверьте предложение AI и подтвердите регистрацию риска." : undefined}
            isDismissable={!create.isPending}
            onOpenChange={(open) => { if (!open && !create.isPending) onClose(); }}
            footer={<>
                <Button disabled={create.isPending} onClick={onClose}>Отмена</Button>
                <Button variant="primary" type="submit" form={formId} disabled={create.isPending}>{create.isPending ? "Создание…" : "Создать риск"}</Button>
            </>}
        >
            <RiskForm projectId={projectId} initial={initial} formId={formId} isSaving={create.isPending} error={create.error?.message} onSave={(input) => create.mutate(input)} />
        </Modal>
    );
}

