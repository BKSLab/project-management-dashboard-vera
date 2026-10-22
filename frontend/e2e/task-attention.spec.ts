import { expect, test } from "@playwright/test";
import { installMockApi, mockState } from "./support/taskMockApi";

test.setTimeout(60_000);

test("просмотр подтверждает только открытый снимок после загрузки содержимого карточки", async ({ page }) => {
    const state = mockState();
    await installMockApi(page, state);
    let releaseComments: () => void = () => {};
    const commentsReady = new Promise<void>((resolve) => { releaseComments = resolve; });
    await page.route("**/api/v1/tasks/100/comments", async (route) => {
        if (route.request().method() === "OPTIONS") return route.fallback();
        await commentsReady;
        return route.fallback();
    });
    await page.goto("/my-tasks");
    await expect(page.getByRole("button", { name: "Новые · 2", exact: true })).toBeVisible();
    expect(state.views).toHaveLength(0);
    await page.getByRole("button", { name: state.tasks[0].title, exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Задача DEMO-1", exact: true })).toBeVisible();
    expect(state.views).toHaveLength(0);
    releaseComments();
    await expect.poll(() => state.views.length).toBe(1);
    expect(state.views[0]).toMatchObject({ taskId: 100, body: { revision: 3, deadline_revision: 1, overdue: false } });
    await expect(page.getByRole("button", { name: "Новые · 1", exact: true })).toBeVisible();
    expect(state.attentionItems[1].is_new).toBe(true);
    expect(state.errors).toEqual([]);
});
