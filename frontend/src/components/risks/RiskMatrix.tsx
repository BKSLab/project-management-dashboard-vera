import { cn } from "@/lib/cn";
import { IMPACT_LABELS, PROBABILITY_LABELS, previewRiskLevel, type RiskMatrixCell, type RiskRating } from "@/lib/risks";
import { RISK_TONES } from "@/lib/risks";

const ROWS: RiskRating[] = ["HIGH", "MEDIUM", "LOW"];
const COLUMNS: RiskRating[] = ["LOW", "MEDIUM", "HIGH"];
const SURFACES = { LOW: "bg-white/[0.025]", MEDIUM: "bg-warning/[0.045]", HIGH: "bg-danger/[0.045]" };

interface Props {
    cells: RiskMatrixCell[];
    probability: RiskRating | null;
    impact: RiskRating | null;
    onSelect: (probability: RiskRating | null, impact: RiskRating | null) => void;
}

export function RiskMatrix({ cells, probability, impact, onSelect }: Props) {
    return (
        <section aria-labelledby="risk-matrix-title" className="rounded-[var(--radius-card)] bg-surface/40 p-4">
            <h2 id="risk-matrix-title" className="text-[11px] font-semibold tracking-[0.09em] text-muted uppercase">Матрица рисков</h2>
            <p className="mt-1 text-[11px] text-muted">Вероятность × влияние</p>
            <table className="mt-4 w-full table-fixed border-separate border-spacing-1.5">
                <caption className="sr-only">Количество рисков по вероятности и влиянию. Выберите ячейку для фильтра реестра.</caption>
                <thead>
                    <tr>
                        <th scope="col" className="w-16"><span className="sr-only">Вероятность</span></th>
                        {COLUMNS.map((value) => <th key={value} scope="col" className="pb-1 text-[10px] font-normal text-muted">{IMPACT_LABELS[value]}<span className="sr-only"> влияние</span></th>)}
                    </tr>
                </thead>
                <tbody>
                    {ROWS.map((p) => (
                        <tr key={p}>
                            <th scope="row" className="text-left text-[10px] font-normal text-muted">{PROBABILITY_LABELS[p]}<span className="sr-only"> вероятность</span></th>
                            {COLUMNS.map((i) => {
                                const count = cells.find((cell) => cell.probability === p && cell.impact === i)?.count ?? 0;
                                const selected = p === probability && i === impact;
                                const label = `${PROBABILITY_LABELS[p]} вероятность, ${IMPACT_LABELS[i].toLowerCase()} влияние: ${count}`;
                                const level = previewRiskLevel(p, i);
                                return (
                                    <td key={i}>
                                        <button
                                            type="button"
                                            aria-label={label}
                                            title={label}
                                            aria-pressed={selected}
                                            onClick={() => onSelect(selected ? null : p, selected ? null : i)}
                                            className={cn("h-14 w-full rounded-control font-mono text-lg transition-colors hover:bg-hover focus-visible:outline-2 focus-visible:outline-accent", RISK_TONES[level], SURFACES[level], selected && "ring-2 ring-accent")}
                                        >{count}</button>
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
            <p className="mt-3 text-[11px] leading-relaxed text-muted">Ячейка фильтрует реестр. Повторное нажатие снимает выбор.</p>
        </section>
    );
}
