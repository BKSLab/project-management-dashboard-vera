import { expect, test } from "@playwright/test";

test("AI-вики показывает покрытие, проблему файла и открывает участника из источников", async ({ page }) => {
    const stamp = "2026-09-07T10:00:00Z";
    const user = { id: 1, username: "anna", first_name: "Анна", last_name: "Иванова", middle_name: null, is_active: true, has_avatar: false };
    const project = { id: 1, owner_id: 1, key: "DEMO", name: "Знания проекта", description_md: "Паспорт", description_sections: null, due_date_has_been_set: false, status: "ACTIVE", color: "#7299cc", icon: null, start_date: null, due_date: null, order_index: 0, created_at: stamp, updated_at: stamp };
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/v1/**", async (route) => {
        const path = new URL(route.request().url()).pathname;
        const headers = { "access-control-allow-origin": "http://127.0.0.1:4179", "access-control-allow-credentials": "true", "access-control-allow-headers": "content-type", "access-control-allow-methods": "GET, POST, OPTIONS" };
        const reply = (json: unknown) => route.fulfill({ status: 200, json, headers });
        if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
        if (path.endsWith("/auth/me")) return reply(user);
        if (path === "/api/v1/projects") return reply([project]);
        if (path === "/api/v1/projects/1") return reply(project);
        if (path.endsWith("/members")) return reply([{ id: 1, project_id: 1, role: "OWNER", user, created_at: stamp }]);
        if (path.endsWith("/knowledge/status")) return reply({ enabled: true, ready: false, points_count: 5, pending_jobs: 0, processing_jobs: 0, failed_jobs: 1, last_error: null, obsolete_points: 0,
            coverage: [{ entity_type: "project", total: 1, indexed: 1, missing: 0, stale: 0 }, { entity_type: "sticker", total: 2, indexed: 1, missing: 1, stale: 0 }, { entity_type: "member", total: 1, indexed: 1, missing: 0, stale: 0 }],
            file_issues: [{ source_id: "attachment:4", title: "scan.pdf", status: "empty", detail: "В файле нет текстового слоя." }] });
        if (path.endsWith("/knowledge/ask")) return reply({ answer: "Руководитель проекта — Анна Иванова.", sources: [{ source_id: "member:1", entity_type: "member", entity_id: 1, title: "Анна Иванова", excerpt: "Роль: OWNER", score: null, task_id: null, document_slug: null, related_source_ids: ["project:1"] }] });
        return reply([]);
    });
    await page.goto("/projects/DEMO/knowledge");
    await expect(page.getByText("Контекст неполный", { exact: true })).toBeVisible();
    await expect(page.getByText("Доступно для поиска", { exact: true })).toBeVisible();
    await expect(page.getByText("1 / 2", { exact: true })).toBeVisible();
    await expect(page.getByText("В файле нет текстового слоя.", { exact: false })).toBeVisible();
    await page.locator("textarea").fill("Кто руководитель проекта?");
    await page.locator("textarea").press("Enter");
    await expect(page.getByText("Руководитель проекта — Анна Иванова.", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Анна Иванова", exact: false }).click();
    await expect(page).toHaveURL(/\/projects\/DEMO\/team$/);
    expect(errors).toEqual([]);
});
