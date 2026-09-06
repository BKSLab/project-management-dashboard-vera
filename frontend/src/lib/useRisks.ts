import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import { formatDateOnly } from "@/lib/dates";
import type { RiskSummary } from "@/lib/risks";

export function useRiskSummary(projectId: number, filters = "") {
    const query = new URLSearchParams(filters);
    query.set("today", formatDateOnly(new Date()));
    const params = query.toString();
    return useQuery({
        queryKey: queryKeys.projectRiskSummary(projectId, params),
        queryFn: () => api.get<RiskSummary>(`${endpoints.projectRiskSummary(projectId)}?${params}`),
        enabled: projectId > 0,
    });
}

export function useRiskTaskCounts(projectId: number) {
    return useQuery({
        queryKey: queryKeys.projectRiskTaskCounts(projectId),
        queryFn: () => api.get<Record<string, number>>(endpoints.projectRiskTaskCounts(projectId)),
        enabled: projectId > 0,
    });
}

export function useInvalidateRisks(projectId: number) {
    const client = useQueryClient();
    return () => Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.project(projectId) }),
        client.invalidateQueries({ queryKey: queryKeys.dashboard }),
    ]);
}
