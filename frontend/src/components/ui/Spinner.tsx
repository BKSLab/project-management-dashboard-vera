import { cn } from "@/lib/cn";

interface SpinnerProps {
    className?: string;
}

// Задержки по порядку ячейки Брайля: левый столбец (точки 1→2→3), правый (4→5→6)
const BRAILLE_DELAYS = [0, 0.375, 0.125, 0.5, 0.25, 0.625];

export function Spinner({ className }: SpinnerProps) {
    return (
        <div
            role="status"
            aria-label="Загрузка..."
            className={cn("flex items-center justify-center", className)}
        >
            <div
                aria-hidden="true"
                className="grid grid-cols-2 gap-x-2 gap-y-2.5"
            >
                {BRAILLE_DELAYS.map((delay, i) => (
                    <div
                        key={i}
                        className="h-3 w-3 rounded-full"
                        style={{
                            animation: `braille-dot 1.5s ease-in-out infinite`,
                            animationDelay: `${delay}s`,
                        }}
                    />
                ))}
            </div>
        </div>
    );
}
