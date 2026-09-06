import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import { RISK_STATUS_LABELS, type RiskPage } from "@/lib/risks";
import { useUiStore } from "@/stores/ui";
import { DrawerSection } from "@/components/ui/Drawer";
import { Button, LinkButton } from "@/components/ui/Button";
import { ErrorMessage } from "@/components/ui/States";
import { RiskBadge } from "@/components/risks/RiskBadge";
import { CreateRiskDialog } from "@/components/risks/CreateRiskDialog";

export function TaskRiskSection({ projectId, projectKey, taskId }: { projectId: number; projectKey: string; taskId: number }) {
    const [creating, setCreating] = useState(false);
    const openRisk = useUiStore((state) => state.setSelectedRisk);
    const openTask = useUiStore((state) => state.setSelectedTaskId);
    const params = `task_id=${taskId}&page_size=5`;
    const query = useQuery({
        queryKey: queryKeys.projectRiskList(projectId, params),
        queryFn: () => api.get<RiskPage>(`${endpoints.projectRisks(projectId)}?${params}`),
    });
    return (
        <DrawerSection title="Риски" count={query.data?.total} action={<Button size="sm" variant="ghost" onClick={() => setCreating(true)}>Добавить</Button>}>
            {query.isPending && <p role="status" className="text-[12px] text-muted">Загрузка связанных рисков…</p>}
            {query.error && <ErrorMessage message={query.error.message} action={<Button onClick={() => void query.refetch()}>Повторить</Button>} />}
            {query.data?.total === 0 && <p className="text-[12px] text-muted">С задачей пока не связаны риски.</p>}
            <ul className="divide-y divide-line-subtle">
                {query.data?.items.map((risk) => <li key={risk.id}>
                    <button type="button" className="flex w-full flex-col gap-1.5 rounded-control px-2 py-2.5 text-left hover:bg-hover focus-visible:outline-2 focus-visible:outline-accent" onClick={() => openRisk({ projectId, riskId: risk.id })}>
                        <span className="flex items-center justify-between gap-2"><span className="font-mono text-[11px] text-muted">{risk.key}</span><RiskBadge level={risk.risk_level} /></span>
                        <span className="text-[13px] text-primary">{risk.title}</span>
                        <span className="text-[11px] text-muted">{RISK_STATUS_LABELS[risk.status]}</span>
                    </button>
                </li>)}
            </ul>
            {(query.data?.total ?? 0) > 5 && <LinkButton to={`/projects/${projectKey}/risks?task_id=${taskId}&status=all`} variant="ghost" className="mt-2" onClick={() => openTask(null)}>Все риски задачи</LinkButton>}
            {creating && <CreateRiskDialog projectId={projectId} initial={{ task_id: taskId }} onClose={() => setCreating(false)} />}
        </DrawerSection>
    );
}

