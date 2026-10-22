// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Project } from "@/lib/types";
import { useChatDockStore } from "@/stores/chatDock";
import { useTimWidgetStore } from "@/stores/timWidget";
import { TimWidget } from "@/components/tim/TimWidget";
import { FloatingChatDock } from "./FloatingChatDock";

vi.mock("@/lib/useProjectChat", () => ({ useProjectChat: () => ({ info: { unread_count: 2 }, error: null }) }));
vi.mock("@/lib/useAuth", () => ({ useCurrentUser: () => ({ data: { id: 1 } }) }));
vi.mock("./ProjectChatWorkspace", () => ({ ProjectChatWorkspace: () => <p>Общий чат</p> }));
vi.mock("@/components/tim/TimPanel", () => ({ TimPanel: () => <section role="dialog" aria-label="Личный виджет Веры" /> }));

const project = { id: 1, key: "DEMO", name: "Личный проект" } as Project;
function Location() {
    const location = useLocation();
    return <output data-testid="location">{location.pathname}{location.search}{location.hash}</output>;
}
function Dock() {
    const panel = useChatDockStore((state) => state.panel);
    return <FloatingChatDock project={project} projects={[project]} userId={1} projectPinned fullPage={null} panel={panel} />;
}
function setup() {
    render(<MemoryRouter initialEntries={["/projects/DEMO/board?task=42&confirm=action-id#context"]}><Dock /><TimWidget /><Location /></MemoryRouter>);
}

beforeEach(() => {
    useChatDockStore.setState({ panel: null, projects: {} });
    useTimWidgetStore.setState({ open: false, conversations: {}, drafts: {} });
});
afterEach(cleanup);

it("оставляет одну командную кнопку и виджет Веры, закрывая личную панель перед общим чатом", async () => {
    setup();
    expect(screen.queryByRole("button", { name: "Открыть чат агента" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Открыть чат команды" })).toHaveLength(1);
    const vera = screen.getByRole("button", { name: "Спросить Веру" });
    expect(vera.title).toContain("Вера — проектный менеджер");
    fireEvent.click(vera);
    await screen.findByRole("dialog", { name: "Личный виджет Веры" });
    fireEvent.click(screen.getByRole("button", { name: "Открыть чат команды" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Личный виджет Веры" })).toBeNull());
    const team = screen.getByRole("dialog", { name: "Окно чата команды" });
    expect(screen.queryByRole("button", { name: "Спросить Веру" })).toBeNull();
    fireEvent.keyDown(team, { key: "Escape" });
    expect(screen.getByRole("button", { name: "Спросить Веру" })).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Открыть чат команды" }));
});

it("разворачивает командный чат, сохраняя query и hash исходной страницы", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Открыть чат команды" }));
    fireEvent.click(screen.getByRole("button", { name: "Открыть чат во вкладке" }));
    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/projects/DEMO/chat?task=42&confirm=action-id#context"));
    expect(useChatDockStore.getState().panel).toBeNull();
});

it("на полной странице чата не создаёт второй командный вход", () => {
    render(<MemoryRouter><FloatingChatDock project={project} projects={[project]} userId={1} projectPinned fullPage="team" panel={null} /><TimWidget /></MemoryRouter>);
    expect(screen.queryByRole("button", { name: "Открыть чат команды" })).toBeNull();
    expect(screen.getByRole("button", { name: "Спросить Веру" })).toBeTruthy();
});
