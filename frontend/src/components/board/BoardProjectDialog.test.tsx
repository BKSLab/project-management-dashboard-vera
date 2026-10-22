// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BoardProjectDialog } from "./BoardProjectDialog";

afterEach(cleanup);
describe("create project from board dialog", () => {
    it("prefills board name, requires a valid key and submits project fields once", async () => {
        let finish!: () => void;
        const create = vi.fn(() => new Promise<void>((resolve) => { finish = resolve; }));
        const close = vi.fn();
        render(<BoardProjectDialog boardTitle="Моя схема" onCreate={create} onClose={close} />);
        expect((screen.getByLabelText("Название") as HTMLInputElement).value).toBe("Моя схема");
        const submit = screen.getByRole("button", { name: "Создать проект" }) as HTMLButtonElement;
        expect(submit.disabled).toBe(true);
        fireEvent.change(screen.getByPlaceholderText("PROJ"), { target: { value: "BOARD" } });
        fireEvent.click(submit); fireEvent.click(submit);
        expect(create).toHaveBeenCalledOnce();
        expect(create).toHaveBeenCalledWith(expect.objectContaining({ key: "BOARD", name: "Моя схема", status: "PLANNING" }));
        fireEvent.click(screen.getByRole("button", { name: "Закрыть" }));
        expect(close).not.toHaveBeenCalled();
        finish();
        await waitFor(() => expect(close).toHaveBeenCalledOnce());
    });
    it("keeps the dialog and values after a failure, then permits retry", async () => {
        const create = vi.fn().mockRejectedValueOnce(new Error("Доска изменилась. Обновите страницу."));
        const close = vi.fn();
        render(<BoardProjectDialog boardTitle="Черновик" onCreate={create} onClose={close} />);
        fireEvent.change(screen.getByPlaceholderText("PROJ"), { target: { value: "TEST" } });
        fireEvent.click(screen.getByRole("button", { name: "Создать проект" }));
        await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Доска изменилась"));
        expect(close).not.toHaveBeenCalled();
        expect((screen.getByPlaceholderText("PROJ") as HTMLInputElement).value).toBe("TEST");
        expect((screen.getByRole("button", { name: "Создать проект" }) as HTMLButtonElement).disabled).toBe(false);
    });
});
