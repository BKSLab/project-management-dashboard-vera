import { Route, Stamp } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ScheduleToolsProps {
    criticalMode: boolean;
    onCriticalModeChange: (value: boolean) => void;
    /** Нет права на правку — кнопки плана нет. */
    onFixPlan?: () => void;
    isFixingPlan: boolean;
}

/** Кнопки шкалы про график: «Критический путь» и «Зафиксировать план». */
export function ScheduleTools({ criticalMode, onCriticalModeChange, onFixPlan, isFixingPlan }: ScheduleToolsProps) {
    return (
        <>
            <Button
                size="sm"
                variant={criticalMode ? "secondary" : "ghost"}
                icon={<Route size={13} aria-hidden="true" />}
                aria-pressed={criticalMode}
                className={criticalMode ? "border-danger/50 text-danger" : undefined}
                title={"Критический путь: подсветить цепочку задач, от которой зависит окончание проекта.\nЗадержка любой из них сдвигает весь проект."}
                onClick={() => onCriticalModeChange(!criticalMode)}
            >
                Критический путь
            </Button>
            {onFixPlan && (
                <Button
                    size="sm"
                    variant="ghost"
                    icon={<Stamp size={13} aria-hidden="true" />}
                    disabled={isFixingPlan}
                    title={"Зафиксировать план проекта: текущие даты всех задач станут базовым планом.\nПотом отклонения видны пунктиром под полосами. Перед записью спросим подтверждение."}
                    onClick={onFixPlan}
                >
                    Зафиксировать план
                </Button>
            )}
        </>
    );
}
