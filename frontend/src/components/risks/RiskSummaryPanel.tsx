import { Link } from "react-router-dom";
import { ArrowUpRight, ShieldAlert } from "lucide-react";
import { RISK_SIGNAL_LABELS, type RiskSummary } from "@/lib/risks";

export function RiskSummaryPanel({ summary, projectKey }: { summary: RiskSummary; projectKey: string }) {
    return (
        <section aria-label="Риски проекта" className="border-t border-line-subtle pt-3">
            <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase"><ShieldAlert size={13} />Риски</h3>
                <Link to={`/projects/${projectKey}/risks`} className="inline-flex items-center gap-1 text-[11px] text-accent hover:text-accent-hover">Открыть реестр <ArrowUpRight size={12} /></Link>
            </div>
            <p className="text-[12px] text-secondary">
                <strong className="font-mono">{summary.active_risks}</strong> активных
                <span className={summary.high_risks ? "ml-3 text-danger" : "ml-3 text-muted"}>{summary.high_risks} HIGH</span>
                <span className={summary.risks_due_for_review ? "ml-3 text-warning" : "ml-3 text-muted"}>{summary.risks_due_for_review} требуют контроля</span>
            </p>
            {summary.signals.length > 0 && <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
                {summary.signals.map((signal) => <li key={signal.code}>{RISK_SIGNAL_LABELS[signal.code]}: <span className="font-mono text-secondary">{signal.count}</span></li>)}
            </ul>}
        </section>
    );
}

