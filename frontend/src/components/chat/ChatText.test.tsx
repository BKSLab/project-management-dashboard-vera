// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatText } from "./ChatText";

describe("текст общего чата", () => {
    it("показывает HTML как текст и поддерживает безопасную цитату", () => {
        const { container } = render(<ChatText content={'<img src=x onerror=alert(1)>\n> **Решение**\n`код` https://example.com javascript:alert(1)'} />);
        expect(container.querySelector("img")).toBeNull();
        expect(container.querySelector("blockquote strong")?.textContent).toBe("Решение");
        expect(screen.getByRole("link").getAttribute("href")).toBe("https://example.com");
        expect(container.textContent).toContain("javascript:alert(1)");
    });
});
