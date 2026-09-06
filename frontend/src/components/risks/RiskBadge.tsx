import { cn } from "@/lib/cn";
import { RISK_LEVEL_LABELS, RISK_TONES, type RiskRating } from "@/lib/risks";

export function RiskBadge({ level }: { level: RiskRating }) {
    return (
        <span aria-label={`Уровень риска: ${RISK_LEVEL_LABELS[level]}`} className={cn("inline-flex shrink-0 items-center gap-1.5 text-[11px] font-medium", RISK_TONES[level])}>
            <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
            <span className="font-mono">{level}</span>
        </span>
    );
}
