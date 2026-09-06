import { useUiStore } from "@/stores/ui";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { AnalyticsPanel } from "@/components/dashboard/AnalyticsPanel";

/**
 * Пульс проекта: подробный разбор одного проекта.
 *
 * Сводка на дашборде отвечает на вопрос «за какой проект браться», а этот
 * экран — «что происходит внутри». Поэтому область анализа здесь не
 * выбирается: она задана самим проектом.
 */
export function ProjectPulsePage() {
    const project = useProjectOutlet();
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);

    return <AnalyticsPanel projectId={project.id} onOpenTask={setSelectedTaskId} />;
}
