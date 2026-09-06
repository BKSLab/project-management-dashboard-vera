import { describe, expect, it } from "vitest";
import { isRiskReviewDue, previewRiskLevel, riskChanges, riskFormError, riskInput, riskQuery } from "./risks";

describe("контракты формы рисков", () => {
    it("очищает серверные поля и сохраняет отдельные планы", () => {
        const saved = { ...riskInput(), title: "  CRM  ", description: "  Причина  ", id: 12, risk_level: "HIGH", mitigation_plan: "Превентивный", response_plan: "При наступлении" };
        const input = riskInput(saved);
        expect(input.title).toBe("CRM");
        expect(input).not.toHaveProperty("id");
        expect(input).not.toHaveProperty("risk_level");
        expect(input.mitigation_plan).not.toBe(input.response_plan);
    });

    it("передаёт очистку ссылок, сохраняя пропущенные поля и источник", () => {
        const before = riskInput({ task_id: 7, owner_user_id: 4, review_date: "2026-09-12" });
        expect(riskChanges(before, { ...before, task_id: null, owner_user_id: null, review_date: null, source: "AI_SUGGESTED" })).toEqual({ task_id: null, owner_user_id: null, review_date: null });
        expect(riskChanges(before, before)).toEqual({});
    });

    it("валидирует обязательное описание и календарную дату", () => {
        expect(riskFormError(riskInput())).toContain("Заполните");
        expect(riskFormError(riskInput({ title: "Риск", description: "Описание", review_date: "2026-02-30" }))).toContain("дату");
        expect(riskFormError(riskInput({ title: "Риск", description: "Описание" }))).toBeNull();
    });

    it("учитывает контроль сегодня и исключает закрытый риск", () => {
        expect(isRiskReviewDue({ status: "OCCURRED", review_date: "2026-09-06" }, "2026-09-06")).toBe(true);
        expect(isRiskReviewDue({ status: "CLOSED", review_date: "2020-01-01" }, "2026-09-06")).toBe(false);
        expect(isRiskReviewDue({ status: "OPEN", review_date: null })).toBe(false);
    });

    it("предпросмотр использует категории, а не проценты", () => {
        expect(previewRiskLevel("HIGH", "MEDIUM")).toBe("HIGH");
        expect(previewRiskLevel("LOW", "HIGH")).toBe("MEDIUM");
        expect(previewRiskLevel("MEDIUM", "LOW")).toBe("LOW");
        expect(new URLSearchParams(riskQuery({ search: "API & CRM", task_id: 7, owner_user_id: null })).get("search")).toBe("API & CRM");
    });
});
