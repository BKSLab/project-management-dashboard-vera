import { describe, expect, it } from "vitest";
import { wheelAction, type WheelInput } from "./wheel";

const base: WheelInput = { deltaX: 0, deltaY: 0, deltaMode: 0, ctrlKey: false, metaKey: false, shiftKey: false };

function factorOf(input: WheelInput): number {
    const action = wheelAction(input);
    if (action.type !== "zoom") throw new Error(`ожидали масштаб, а не ${action.type}`);
    return action.factor;
}

describe("wheelAction", () => {
    it("колесо вниз уменьшает масштаб, вверх — увеличивает", () => {
        expect(factorOf({ ...base, deltaY: 100 })).toBeLessThan(1);
        expect(factorOf({ ...base, deltaY: -100 })).toBeGreaterThan(1);
        expect(factorOf({ ...base, deltaY: 100 }) * factorOf({ ...base, deltaY: -100 })).toBeCloseTo(1);
    });

    it("дробный шаг (RDP, масштаб экрана Windows) и строки Firefox — тоже масштаб", () => {
        expect(factorOf({ ...base, deltaY: 83.33333 })).toBeLessThan(1);
        expect(factorOf({ ...base, deltaY: 3, deltaMode: 1 })).toBeLessThan(1);
        expect(factorOf({ ...base, deltaY: 4 })).toBeLessThan(1);
    });

    it("огромный шаг не прыгает масштабом больше ~20%", () => {
        expect(factorOf({ ...base, deltaY: 2000 })).toBeGreaterThan(0.79);
    });

    it("щипок на тачпаде (Ctrl+колесо) — масштаб", () => {
        expect(factorOf({ ...base, deltaY: 3.2, ctrlKey: true })).toBeLessThan(1);
    });

    it("Shift + колесо и горизонтальный жест тачпада двигают вбок", () => {
        expect(wheelAction({ ...base, deltaY: 100, shiftKey: true })).toEqual({ type: "pan", dx: 100, dy: 0 });
        expect(wheelAction({ ...base, deltaX: 30, deltaY: 5 })).toEqual({ type: "pan", dx: 30, dy: 0 });
    });
});
