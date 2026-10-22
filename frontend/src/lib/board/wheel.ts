/**
 * Что делает колесо над холстом доски — как в Miro:
 * - колесо (вверх/вниз) — масштаб у курсора, всегда: мышь от тачпада по событию надёжно
 *   не отличить (через RDP и при масштабе экрана Windows шаг колёсика приходит дробным);
 * - щипок на тачпаде (браузер шлёт его как Ctrl+колесо) — тоже масштаб;
 * - Shift + колесо и горизонтальный жест тачпада — прокрутка вбок.
 */

export interface WheelInput {
    deltaX: number;
    deltaY: number;
    /** 0 — пиксели, 1 — строки (Firefox), 2 — страницы. */
    deltaMode: number;
    ctrlKey: boolean;
    metaKey: boolean;
    shiftKey: boolean;
}

export type WheelAction = { type: "zoom"; factor: number } | { type: "pan"; dx: number; dy: number };

const LINE_PX = 33;
const PAGE_PX = 800;
const ZOOM_SPEED = 0.0015;
/** Один «щелчок» не должен менять масштаб больше чем на ~20%, как бы крупно ни пришёл шаг. */
const MAX_STEP = 150;

function toPixels(delta: number, mode: number): number {
    if (mode === 1) return delta * LINE_PX;
    if (mode === 2) return delta * PAGE_PX;
    return delta;
}

function zoomFactor(dy: number): number {
    const clamped = Math.max(-MAX_STEP, Math.min(MAX_STEP, dy));
    return Math.exp(-clamped * ZOOM_SPEED);
}

export function wheelAction(input: WheelInput): WheelAction {
    const dx = toPixels(input.deltaX, input.deltaMode);
    const dy = toPixels(input.deltaY, input.deltaMode);
    if (input.ctrlKey || input.metaKey) return { type: "zoom", factor: zoomFactor(dy) };
    if (input.shiftKey) return { type: "pan", dx: dx === 0 ? dy : dx, dy: 0 };
    if (Math.abs(dx) > Math.abs(dy)) return { type: "pan", dx, dy: 0 };
    return { type: "zoom", factor: zoomFactor(dy) };
}
