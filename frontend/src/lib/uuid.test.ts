import { describe, expect, it, vi } from "vitest";
import { newUuid } from "./uuid";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("newUuid", () => {
    it("возвращает валидный UUID v4", () => {
        expect(newUuid()).toMatch(UUID_V4);
        expect(newUuid()).not.toBe(newUuid());
    });

    it("работает без crypto (http по IP — не secure context)", () => {
        const original = globalThis.crypto;
        vi.stubGlobal("crypto", undefined);
        try {
            expect(newUuid()).toMatch(UUID_V4);
            expect(newUuid()).not.toBe(newUuid());
        } finally {
            vi.stubGlobal("crypto", original);
        }
    });
});
