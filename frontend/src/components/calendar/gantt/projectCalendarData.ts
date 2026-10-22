import { api, endpoints } from "@/lib/api";
import type { TimelineRange } from "@/lib/calendar";
import { mergeProjectCalendars, splitRange } from "@/lib/ganttView";
import type { ProjectCalendar } from "@/lib/types";

/**
 * Календарь проекта за любой период: сервис отдаёт не больше 371 дня за запрос, поэтому
 * длинный срок (весь проект, выгрузка) запрашивается кусками и склеивается. Обычный период
 * календаря — один кусок, запрос тот же, что и раньше.
 */
export async function fetchProjectCalendarRange(
    projectId: number,
    commonParams: URLSearchParams,
    range: TimelineRange,
): Promise<ProjectCalendar> {
    const parts = await Promise.all(
        splitRange(range).map((chunk) => {
            const params = new URLSearchParams(commonParams);
            params.set("date_from", chunk.dateFrom);
            params.set("date_to", chunk.dateTo);
            return api.get<ProjectCalendar>(`${endpoints.projectCalendar(projectId)}?${params.toString()}`);
        }),
    );
    return mergeProjectCalendars(parts);
}
