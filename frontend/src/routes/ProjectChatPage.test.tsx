// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ProjectChatPage } from "./ProjectChatPage";

vi.mock("@/lib/useProjectOutlet", () => ({ useProjectOutlet: () => ({ id: 1, key: "DEMO" }) }));
vi.mock("@/components/chat/ProjectChatWorkspace", () => ({ ProjectChatWorkspace: () => <p>Общая переписка команды</p> }));
vi.mock("@/components/agent/ProjectAgentWorkspace", () => ({ ProjectAgentWorkspace: ({ knowledgeOnly }: { knowledgeOnly: boolean }) => <p>{knowledgeOnly ? "Диагностика индекса" : "Сохранённые личные диалоги"}</p> }));

function Location() {
    const location = useLocation();
    return <output data-testid="location">{location.pathname}{location.search}{location.hash}</output>;
}

afterEach(cleanup);

it("открывает общий чат по умолчанию, а личную историю и знания — из одного меню", async () => {
    render(<MemoryRouter initialEntries={["/projects/DEMO/chat?conversation=17&task=42&confirm=action-id#context"]}><ProjectChatPage /><Location /></MemoryRouter>);
    expect(screen.getByText("Общая переписка команды")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Личные диалоги и знания" }));
    fireEvent.click(screen.getByRole("button", { name: "Личные диалоги" }));
    await screen.findByText("Сохранённые личные диалоги");
    expect(screen.getByText("Личные диалоги по проекту · видите только вы")).toBeTruthy();
    expect(screen.queryByText("Общая переписка команды")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Личные диалоги и знания" }));
    fireEvent.click(screen.getByRole("button", { name: "Знания проекта" }));
    await screen.findByText("Диагностика индекса");
    expect(screen.queryByText("Сохранённые личные диалоги")).toBeNull();
    const url = new URL(screen.getByTestId("location").textContent!, "http://local");
    expect(url.searchParams.get("view")).toBe("knowledge");
    expect(url.searchParams.get("conversation")).toBe("17");
    expect(url.searchParams.get("task")).toBe("42");
    expect(url.searchParams.get("confirm")).toBe("action-id");
    expect(url.hash).toBe("#context");
    fireEvent.click(screen.getByRole("button", { name: "Общий чат" }));
    await waitFor(() => expect(screen.getByText("Общая переписка команды")).toBeTruthy());
    expect(new URL(screen.getByTestId("location").textContent!, "http://local").searchParams.has("view")).toBe(false);
});
