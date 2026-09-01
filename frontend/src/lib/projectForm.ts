import type { Project, ProjectStatus } from "@/lib/types";
import { PROJECT_COLORS } from "@/lib/types";

export interface ProjectFormValues {
    key: string;
    name: string;
    description_md: string;
    status: ProjectStatus;
    color: string;
    icon: string;
    start_date: string;
    due_date: string;
}

export const EMPTY_PROJECT_FORM: ProjectFormValues = {
    key: "",
    name: "",
    description_md: "",
    status: "PLANNING",
    color: PROJECT_COLORS[0],
    icon: "",
    start_date: "",
    due_date: "",
};

export const PROJECT_KEY_PATTERN = /^[A-Za-z][A-Za-z0-9]{1,9}$/;

export function toProjectFormValues(project: Project): ProjectFormValues {
    return {
        key: project.key,
        name: project.name,
        description_md: project.description_md ?? "",
        status: project.status,
        color: project.color,
        icon: project.icon ?? "",
        start_date: project.start_date ?? "",
        due_date: project.due_date ?? "",
    };
}

/** Готовит тело запроса: пустые строки превращаются в null. */
export function toProjectPayload(values: ProjectFormValues) {
    return {
        key: values.key.toUpperCase(),
        name: values.name.trim(),
        description_md: values.description_md.trim() || null,
        status: values.status,
        color: values.color,
        icon: values.icon.trim() || null,
        start_date: values.start_date || null,
        due_date: values.due_date || null,
    };
}

/** Код проекта участвует в номерах задач, поэтому у существующего проекта он не меняется. */
export function toProjectUpdatePayload(values: ProjectFormValues) {
    const { key, ...rest } = toProjectPayload(values);
    void key;
    return rest;
}

export function isProjectFormValid(values: ProjectFormValues): boolean {
    return PROJECT_KEY_PATTERN.test(values.key) && values.name.trim().length > 0;
}
