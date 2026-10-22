// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { BoardActions, type BoardActionsProps } from "./BoardActions";

afterEach(cleanup);
function props(patch: Partial<BoardActionsProps> = {}): BoardActionsProps {
    return { selectedCount: 3, editable: true, hasLockedSelection: false, hasGroupSelection: true,
        templates: [{ id: "template", name: "Схема" }], onAlign: vi.fn(), onDistribute: vi.fn(),
        onGroup: vi.fn(), onUngroup: vi.fn(), onSetLocked: vi.fn(), onSaveTemplate: vi.fn(),
        onInsertTemplate: vi.fn(), onDeleteTemplate: vi.fn(), onExport: vi.fn(), ...patch };
}
describe("BoardActions", () => {
    it("dispatches layout callbacks without owning persistence/history", () => {
        const callbacks = props(); render(<BoardActions {...callbacks} />);
        fireEvent.click(screen.getByRole("button", { name: "По левому краю" }));
        fireEvent.click(screen.getByRole("button", { name: "Равные интервалы по вертикали" }));
        expect(callbacks.onAlign).toHaveBeenCalledWith("left");
        expect(callbacks.onDistribute).toHaveBeenCalledWith("vertical");
    });
    it("requires names, trims them, inserts by ID and can remove a template", () => {
        const callbacks = props(); render(<BoardActions {...callbacks} />);
        expect((screen.getByRole("button", { name: "Сгруппировать" }) as HTMLButtonElement).disabled).toBe(true);
        fireEvent.change(screen.getByLabelText("Название группы или шаблона"), { target: { value: "  Новая  " } });
        fireEvent.click(screen.getByRole("button", { name: "Сгруппировать" }));
        fireEvent.click(screen.getByRole("button", { name: "Сохранить выделение как шаблон" }));
        fireEvent.change(screen.getByLabelText("Шаблон доски"), { target: { value: "template" } });
        fireEvent.click(screen.getByRole("button", { name: "Вставить шаблон" }));
        fireEvent.click(screen.getByRole("button", { name: "Удалить шаблон" }));
        expect(callbacks.onGroup).toHaveBeenCalledWith("Новая");
        expect(callbacks.onSaveTemplate).toHaveBeenCalledWith("Новая");
        expect(callbacks.onInsertTemplate).toHaveBeenCalledWith("template");
        expect(callbacks.onDeleteTemplate).toHaveBeenCalledWith("template");
    });
    it("can unlock a locked selection but cannot align or ungroup it", () => {
        const callbacks = props({ hasLockedSelection: true }); render(<BoardActions {...callbacks} />);
        fireEvent.click(screen.getByRole("button", { name: "Разблокировать" }));
        expect(callbacks.onSetLocked).toHaveBeenCalledWith(false);
        expect((screen.getByRole("button", { name: "Разгруппировать" }) as HTMLButtonElement).disabled).toBe(true);
        expect((screen.getByRole("button", { name: "По левому краю" }) as HTMLButtonElement).closest("fieldset")!.disabled).toBe(true);
    });
    it("allows read-only exports, including selection, and blocks mutation", () => {
        const callbacks = props({ editable: false }); render(<BoardActions {...callbacks} />);
        fireEvent.change(screen.getByLabelText("Что выгрузить"), { target: { value: "selection" } });
        fireEvent.click(screen.getByRole("button", { name: "Выгрузить SVG" }));
        expect(callbacks.onExport).toHaveBeenCalledWith("svg", "selection");
        expect((screen.getByRole("button", { name: "Заблокировать" }) as HTMLButtonElement).closest("fieldset")!.disabled).toBe(true);
    });
    it("disables stale empty-selection export and hides promotion on project boards", () => {
        const callbacks = props();
        const { rerender } = render(<BoardActions {...callbacks} />);
        fireEvent.change(screen.getByLabelText("Что выгрузить"), { target: { value: "selection" } });
        rerender(<BoardActions {...callbacks} selectedCount={0} />);
        expect((screen.getByRole("button", { name: "Выгрузить PNG" }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.queryByRole("button", { name: "Создать проект из доски" })).toBeNull();
    });
    it("provides a separate promotion command and honours busy state", () => {
        const create = vi.fn(); const callbacks = props({ canCreateProject: true, onCreateProject: create });
        const { rerender } = render(<BoardActions {...callbacks} />);
        fireEvent.click(screen.getByRole("button", { name: "Создать проект из доски" }));
        expect(create).toHaveBeenCalledOnce();
        rerender(<BoardActions {...callbacks} busy />);
        expect((screen.getByRole("button", { name: "Создать проект из доски" }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.queryByText(/Копировать между/)).toBeNull();
    });
});
