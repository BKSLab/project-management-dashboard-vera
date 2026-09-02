import { describe, expect, it } from "vitest";
import {
    EMPTY_PROJECT_FORM,
    isProjectFormValid,
    toProjectPayload,
    toProjectUpdatePayload,
    type ProjectFormValues,
} from "@/lib/projectForm";

const VALID: ProjectFormValues = {
    ...EMPTY_PROJECT_FORM,
    key: "proj",
    name: "  Тестовый проект  ",
    description_md: "  ",
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
        expect(payload.description_md).toBeNull();
        expect(payload.icon).toBe("🚀");
        expect(payload.start_date).toBeNull();
        expect(payload.due_date).toBe("2026-12-20");
    });
});

describe("toProjectUpdatePayload", () => {
    it("не отправляет код проекта: он участвует в номерах задач", () => {
        expect(toProjectUpdatePayload(VALID)).not.toHaveProperty("key");
        expect(toProjectUpdatePayload(VALID).name).toBe("Тестовый проект");
    });
});
