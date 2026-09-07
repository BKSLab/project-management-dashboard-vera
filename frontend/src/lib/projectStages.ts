import type { ProjectStage } from "@/lib/types";

export type StageDraft = Pick<ProjectStage, "name" | "color" | "is_done_stage"> & { draftId: string };

export function validStageDrafts(stages: StageDraft[]): boolean {
    const names = stages.map((stage) => stage.name.trim().toLocaleLowerCase());
    return stages.length > 0 && stages.length <= 30 && names.every(Boolean)
        && new Set(names).size === names.length;
}
