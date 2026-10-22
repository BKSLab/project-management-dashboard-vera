// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { afterEach, expect, it } from "vitest";
import { ProjectChatRedirect } from "./ProjectChatRedirect";
import { ProjectAgentPage } from "@/routes/ProjectAgentPage";

function Location() {
    const location = useLocation();
    const navigate = useNavigate();
    return <><output data-testid="location">{location.pathname}{location.search}{location.hash}</output><button onClick={() => navigate(-1)}>Назад</button></>;
}

afterEach(cleanup);

it.each([["agent", "personal"], ["knowledge", "knowledge"]])("перенаправляет /%s в чат, сохраняя личный контекст, query/hash и историю браузера", async (path, view) => {
    render(<MemoryRouter initialEntries={["/previous", `/projects/DEMO/${path}?conversation=17&confirm=action-id&task=42&tag=a&tag=b#message-5`]} initialIndex={1}>
        <Routes>
            <Route path="/previous" element={<Location />} />
            <Route path="/projects/:projectKey">
                <Route path="agent" element={<ProjectAgentPage />} />
                <Route path="knowledge" element={<ProjectChatRedirect view="knowledge" />} />
                <Route path="chat" element={<Location />} />
            </Route>
        </Routes>
    </MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId("location").textContent).toContain("/projects/DEMO/chat?"));
    const url = new URL(screen.getByTestId("location").textContent!, "http://local");
    expect(url.searchParams.get("view")).toBe(view);
    expect(url.searchParams.get("conversation")).toBe("17");
    expect(url.searchParams.get("confirm")).toBe("action-id");
    expect(url.searchParams.get("task")).toBe("42");
    expect(url.searchParams.getAll("tag")).toEqual(["a", "b"]);
    expect(url.hash).toBe("#message-5");
    fireEvent.click(screen.getByRole("button", { name: "Назад" }));
    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/previous"));
});
