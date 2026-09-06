// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it } from "vitest";
import { RiskMatrix } from "./RiskMatrix";
import type { RiskRating } from "@/lib/risks";

afterEach(cleanup);

it("все девять ячеек доступны с клавиатуры и повторный выбор снимает фильтр", async () => {
    function Matrix() {
        const [pair, setPair] = useState<[RiskRating | null, RiskRating | null]>([null, null]);
        return <RiskMatrix cells={[{ probability: "HIGH", impact: "HIGH", count: 42 }]} probability={pair[0]} impact={pair[1]} onSelect={(p, i) => setPair([p, i])} />;
    }
    render(<Matrix />);
    const user = userEvent.setup();
    expect(screen.getAllByRole("button")).toHaveLength(9);
    const cell = screen.getByRole("button", { name: "Высокая вероятность, высокое влияние: 42" });
    cell.focus();
    await user.keyboard("{Enter}");
    expect(cell.getAttribute("aria-pressed")).toBe("true");
    await user.keyboard(" ");
    expect(cell.getAttribute("aria-pressed")).toBe("false");
});
