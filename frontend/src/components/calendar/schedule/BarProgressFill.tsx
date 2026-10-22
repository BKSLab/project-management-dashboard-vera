import { barProgress } from "@/lib/ganttSchedule";

/** Заливка полосы слева на процент выполнения; без прогресса ничего не рисует. */
export function BarProgressFill({ progress }: { progress: number | null | undefined }) {
    const value = barProgress(progress);
    if (value === null || value === 0) return null;
    return (
        <span
            aria-hidden="true"
            data-bar-progress={value}
            className="pointer-events-none absolute inset-y-0 left-0 -z-10 bg-success/25"
            style={{ width: `${value}%` }}
        />
    );
}
