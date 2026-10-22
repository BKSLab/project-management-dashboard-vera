// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { queryKeys } from "@/lib/api";
import { ChatWorkspace } from "./ChatWorkspace";

vi.mock("@/lib/useAuth", () => ({ useCurrentUser: () => ({ data: { id: 1 } }) }));
vi.mock("./FloatingChatDock", () => ({ FloatingChatDock: () => null }));
vi.mock("./ProjectChatProvider", () => ({ ProjectChatProvider: ({ chatVisible, children }: { chatVisible: boolean; children: ReactNode }) => <><output data-testid="visible">{String(chatVisible)}</output>{children}</> }));

afterEach(cleanup);

it.each([["/projects/DEMO/chat", true], ["/projects/DEMO/chat?view=personal", false], ["/projects/DEMO/chat?view=knowledge", false], ["/projects/DEMO/team", false]])("считает общий чат видимым только в его представлении: %s", (path, visible) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    client.setQueryData(queryKeys.projects, [{ id: 1, key: "DEMO" }]);
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/projects/:projectKey/*" element={<ChatWorkspace><p>Содержимое</p></ChatWorkspace>} /></Routes></MemoryRouter></QueryClientProvider>);
    expect(screen.getByTestId("visible").textContent).toBe(String(visible));
    client.clear();
});
