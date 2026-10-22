// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { api } from "@/lib/api";
import { useTaskViewed } from "./useTaskViewed";

vi.mock("@/lib/useAuth", () => ({ useCurrentUser: () => ({ data: { id: 7 } }) }));
vi.mock("@/lib/api", () => ({ api: { post: vi.fn().mockResolvedValue(undefined) } }));

let intersection: ((entries: { isIntersecting: boolean }[]) => void) | undefined;
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });

it("не сбрасывает счётчик скрытой карточки и подтверждает только загруженную версию", async () => {
    vi.stubGlobal("IntersectionObserver", class {
        constructor(callback: typeof intersection) { intersection = callback; }
        observe() {}
        disconnect() {}
    });
    const client = new QueryClient();
    const node = document.createElement("div");
    document.body.append(node);
    const ref = { current: node };
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const view = { revision: 4, deadline_revision: 2, overdue: true };
    const { rerender, unmount } = renderHook(({ token }) => useTaskViewed(42, token, ref), { initialProps: { token: view }, wrapper });
    act(() => intersection?.([{ isIntersecting: false }]));
    expect(api.post).not.toHaveBeenCalled();
    act(() => intersection?.([{ isIntersecting: true }]));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/api/v1/tasks/42/view", view));
    rerender({ token: { ...view } });
    act(() => intersection?.([{ isIntersecting: true }]));
    expect(api.post).toHaveBeenCalledTimes(1);
    unmount();
    node.remove();
});

it("не подтверждает просмотр, пока данные не загрузились", () => {
    const client = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    renderHook(() => useTaskViewed(42, undefined, { current: null }), { wrapper });
    expect(api.post).not.toHaveBeenCalled();
});
