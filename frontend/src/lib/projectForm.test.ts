import { describe, expect, it } from "vitest";
import {
    EMPTY_PROJECT_FORM,
    isProjectFormValid,
    toProjectPayload,
    toProjectUpdatePayload,
    toProjectFormValues,
    requiresDeadlineComment,
    type ProjectFormValues,
} from "@/lib/projectForm";
import type { Project } from "@/lib/types";

const VALID: ProjectFormValues = {
    ...EMPTY_PROJECT_FORM,
    key: "proj",
    name: "  Тестовый проект  ",
    icon: " 🚀 ",
    due_date: "2026-12-20",
};

describe("isProjectFormValid", () => {
    it("требует корректный код и непустое название", () => {
        expect(isProjectFormValid(VALID)).toBe(true);
        expect(isProjectFormValid({ ...VALID, key: "V" })).toBe(false);
        expect(isProjectFormValid({ ...VALID, key: "1PROJ" })).toBe(false);
        expect(isProjectFormValid({ ...VALID, key: "PROJPROJPROJ" })).toBe(false);
        expect(isProjectFormValid({ ...VALID, name: "   " })).toBe(false);
    });
});

describe("toProjectPayload", () => {
    it("нормализует код, обрезает строки и заменяет пустые значения на null", () => {
        const payload = toProjectPayload(VALID);

        expect(payload.key).toBe("PROJ");
        expect(payload.name).toBe("Тестовый проект");
        expect(payload.description_sections).toEqual(EMPTY_PROJECT_FORM.description_sections);
        expect(payload.icon).toBe("🚀");
        expect(payload.start_date).toBeNull();
        expect(payload.due_date).toBe("2026-12-20");
    });
});

const PROJECT: Project = {
    id: 7, key: "PROJ", name: "Проект", description_md: "Старое **описание**",
    status: "ACTIVE", color: "#58a6ff", icon: null, start_date: "2026-09-01",
    due_date: "2026-12-20", order_index: 0, created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
};

describe("паспорт и сроки", () => {
    it("сохраняет старое описание целиком в дополнительных сведениях", () => {
        expect(toProjectFormValues(PROJECT).description_sections.additional).toBe(PROJECT.description_md);
    });

    it("исключает неизменённый срок из PATCH, чтобы не затереть чужой перенос", () => {
        const payload = toProjectUpdatePayload(toProjectFormValues(PROJECT), PROJECT);
        expect(payload).not.toHaveProperty("due_date");
        expect(payload).not.toHaveProperty("due_date_comment");
    });

    it("передаёт исходный срок и причину его удаления", () => {
        const values = { ...toProjectFormValues(PROJECT), due_date: "", due_date_comment: "  Перепланирование  " };
        expect(requiresDeadlineComment(PROJECT, values)).toBe(true);
        expect(toProjectUpdatePayload(values, PROJECT)).toMatchObject({
            due_date: null, expected_due_date: "2026-12-20", due_date_comment: "Перепланирование",
        });
    });

    it("различает первое назначение и возврат срока после удаления", () => {
        const undated = { ...PROJECT, due_date: null, due_date_has_been_set: false };
        expect(requiresDeadlineComment(undated, VALID)).toBe(false);
        expect(requiresDeadlineComment({ ...undated, due_date_has_been_set: true }, VALID)).toBe(true);
        expect(requiresDeadlineComment(PROJECT, toProjectFormValues(PROJECT))).toBe(false);
    });

    it("отклоняет обратный период и несуществующие даты, разрешает открытый период", () => {
        expect(isProjectFormValid({ ...VALID, start_date: "2027-01-01" })).toBe(false);
        expect(isProjectFormValid({ ...VALID, due_date: "2026-02-30" })).toBe(false);
        expect(isProjectFormValid({ ...VALID, start_date: "2026-09-07", due_date: "" })).toBe(true);
    });
});

describe("toProjectUpdatePayload", () => {
    it("не отправляет код проекта: он участвует в номерах задач", () => {
        expect(toProjectUpdatePayload(VALID)).not.toHaveProperty("key");
        expect(toProjectUpdatePayload(VALID).name).toBe("Тестовый проект");
    });
});
