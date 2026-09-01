import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { daysUntil, dueTone, toDateInputValue } from "@/lib/dates";

const TODAY = new Date(2026, 8, 1, 12, 0, 0);

function isoDay(offsetDays: number): string {
    const date = new Date(TODAY);
    date.setDate(date.getDate() + offsetDays);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
        date.getDate(),
    ).padStart(2, "0")}`;
}

beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(TODAY);
});

afterEach(() => {
    vi.useRealTimers();
});

describe("daysUntil", () => {
    it("считает разницу в днях без учёта времени суток", () => {
        expect(daysUntil(isoDay(0))).toBe(0);
        expect(daysUntil(isoDay(3))).toBe(3);
        expect(daysUntil(isoDay(-2))).toBe(-2);
    });

    it("возвращает null для некорректной даты", () => {
        expect(daysUntil("не дата")).toBeNull();
    });
});

describe("dueTone", () => {
    it("помечает просроченный срок как опасность", () => {
        expect(dueTone(isoDay(-1))).toBe("danger");
    });

    it("помечает срок в пределах недели как предупреждение", () => {
        expect(dueTone(isoDay(0))).toBe("warning");
        expect(dueTone(isoDay(7))).toBe("warning");
    });

    it("оставляет дальний срок приглушённым", () => {
        expect(dueTone(isoDay(8))).toBe("muted");
        expect(dueTone(null)).toBe("muted");
    });

    it("не подсвечивает срок выполненной задачи", () => {
        expect(dueTone(isoDay(-5), true)).toBe("muted");
    });
});

describe("toDateInputValue", () => {
    it("обрезает ISO-строку до даты", () => {
        expect(toDateInputValue("2026-09-08T10:00:00Z")).toBe("2026-09-08");
        expect(toDateInputValue(null)).toBe("");
    });
});
