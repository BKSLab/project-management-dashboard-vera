import { CheckCircle2, CircleAlert, Clock3, XCircle } from "lucide-react";
import type { AgentToolRun, KnowledgeSource, Project } from "@/lib/types";
import { actionSources } from "@/lib/agentCards";
import { AgentEntityCard } from "@/components/agent/AgentEntityCard";
import { Button } from "@/components/ui/Button";

const LABELS: Record<string, string> = {
    task_id: "Задача", task_key: "Ключ задачи", title: "Название", name: "Название", body_md: "Текст",
    description_md: "Описание", stage_id: "Стадия", position: "Позиция", changes: "Изменения",
    user_id: "Участник", username: "Логин", comment_id: "Комментарий", document_id: "Документ",
    attachment_id: "Файл", sticker_id: "Стикер", node_id: "Раздел ИСР", milestone_id: "Веха",
    dependency_id: "Зависимость", risk_id: "Риск", revision: "Версия", expected_updated_at: "Прочитанная версия",
    expected_body_md: "Прежний текст", start_date: "Начало", due_date: "Срок", planned_start: "Начало",
    planned_end: "Окончание", expected_version: "Прочитанная версия", reason: "Причина",
    checklist: "Чек-лист", checklist_revision: "Версия чек-листа", parent_id: "Родительский раздел",
};

function Parameters({ value }: { value: unknown }) {
    if (value == null) return <span>Не задано</span>;
    if (Array.isArray(value)) return <ol className="list-decimal space-y-1 pl-4">{value.map((item, index) => <li key={index}><Parameters value={item} /></li>)}</ol>;
    if (typeof value === "object") return <dl className="space-y-1">{Object.entries(value).map(([key, item]) => (
        <div key={key}><dt className="font-medium">{LABELS[key] ?? key}</dt><dd className="whitespace-pre-wrap break-words pl-2"><Parameters value={item} /></dd></div>
    ))}</dl>;
    return <span>{String(value)}</span>;
}

export function AgentActionCard({ action, project, sources, enabled, pending, onDecision }: {
    action: AgentToolRun;
    project: Project;
    sources: KnowledgeSource[];
    enabled: boolean;
    pending: boolean;
    onDecision: (decision: "approve" | "reject") => void;
}) {
    const status = { pending: "Ожидает решения", completed: "Выполнено", rejected: "Отклонено", failed: "Не выполнено" }[action.status];
    const Icon = { pending: Clock3, completed: CheckCircle2, rejected: XCircle, failed: CircleAlert }[action.status];
    const cards = actionSources(action);
    return <section aria-label={`Действие: ${action.title}`} className="mt-3 rounded-md border border-line bg-surface/80 p-3 text-[12px]">
        <p className="font-medium text-primary">{action.title}</p>
        <p role="status" className={`mt-1 flex items-center gap-1.5 ${action.status === "completed" ? "text-success" : action.status === "failed" ? "text-danger" : "text-muted"}`}><Icon size={13} />{status}</p>
        {cards.length > 0 && <div className="mt-3 space-y-2">{cards.map((source) => <AgentEntityCard key={source.source_id} source={action.status === "completed" ? sources.find((item) => item.source_id === source.source_id) ?? source : source} project={project} />)}</div>}
        {!cards.length && action.result.preview != null && action.status === "pending" && <div className="mt-2"><Parameters value={action.result.preview} /></div>}
        {typeof action.result.message === "string" && <p className="mt-2 text-secondary">{action.result.message}</p>}
        {typeof action.result.error === "string" && <p className="mt-2 text-danger">{action.result.error}</p>}
        <details open={action.status === "pending"} className="mt-2">
            <summary className="cursor-pointer text-secondary">Параметры действия</summary>
            <div className="mt-2 max-h-64 overflow-y-auto"><Parameters value={action.arguments} /></div>
        </details>
        {action.status === "pending" && <div className="mt-3 flex gap-2">
            <Button size="sm" variant="primary" disabled={!enabled || pending} onClick={() => onDecision("approve")}>Подтвердить</Button>
            <Button size="sm" disabled={!enabled || pending} onClick={() => onDecision("reject")}>Отклонить</Button>
        </div>}
    </section>;
}
