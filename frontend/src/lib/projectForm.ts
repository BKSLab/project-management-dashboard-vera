import type { Project, ProjectDescription, ProjectStatus, ProjectUpdate } from "@/lib/types";
import { PROJECT_COLORS } from "@/lib/types";
import { parseDateOnly } from "@/lib/dates";

export interface ProjectFormValues {
    key: string;
    name: string;
    description_sections: ProjectDescription;
    status: ProjectStatus;
    color: string;
    icon: string;
    start_date: string;
    due_date: string;
    due_date_comment: string;
}

export const EMPTY_PROJECT_FORM: ProjectFormValues = {
    key: "",
    name: "",
    description_sections: { problem: "", goal: "", expected_result: "", additional: "" },
    status: "PLANNING",
    color: PROJECT_COLORS[0],
    icon: "",
    start_date: "",
    due_date: "",
    due_date_comment: "",
};

export const PROJECT_KEY_PATTERN = /^[A-Za-z][A-Za-z0-9]{1,9}$/;

export function toProjectFormValues(project: Project): ProjectFormValues {
    return {
        key: project.key,
        name: project.name,
        description_sections: project.description_sections ?? {
            problem: "", goal: "", expected_result: "", additional: project.description_md ?? "",
        },
        status: project.status,
        color: project.color,
        icon: project.icon ?? "",
        start_date: project.start_date ?? "",
        due_date: project.due_date ?? "",
        due_date_comment: "",
    };
}

/** Готовит тело запроса: пустые строки превращаются в null. */
export function toProjectPayload(values: ProjectFormValues) {
    return {
        key: values.key.toUpperCase(),
        name: values.name.trim(),
        description_sections: values.description_sections,
        status: values.status,
        color: values.color,
        icon: values.icon.trim() || null,
        start_date: values.start_date || null,
        due_date: values.due_date || null,
    };
}

/** Код проекта участвует в номерах задач, поэтому у существующего проекта он не меняется. */
export function toProjectUpdatePayload(values: ProjectFormValues, project?: Project): ProjectUpdate {
    const { key, ...rest } = toProjectPayload(values);
    void key;
    if (project && rest.due_date === project.due_date) {
        const { due_date, ...unchangedDeadline } = rest;
        void due_date;
        return unchangedDeadline;
    }
    if (project) return { ...rest, expected_due_date: project.due_date, due_date_comment: values.due_date_comment.trim() };
    return rest;
}

export function isProjectFormValid(values: ProjectFormValues): boolean {
    return PROJECT_KEY_PATTERN.test(values.key) && values.name.trim().length > 0
        && (!values.start_date || parseDateOnly(values.start_date) !== null)
        && (!values.due_date || parseDateOnly(values.due_date) !== null)
        && !(values.start_date && values.due_date && values.due_date < values.start_date);
}

export function requiresDeadlineComment(project: Project, values: ProjectFormValues): boolean {
    return (project.due_date_has_been_set || project.due_date !== null)
        && (values.due_date || null) !== project.due_date;
}
