import { expect, test } from "@playwright/test";
import { installMockApi, mockState } from "./support/mockApi";

/**
 * Раздел «Доски»: личные доски без проекта (docs/boards-contract.md, «Свободные доски»).
 * Тот же редактор, что у проекта; стикер не связывается с задачами; последнюю доску удалить можно.
 */

test("личная доска: создать из пустого раздела, поставить стикер без задач, удалить последнюю", async ({ page }) => {
    const state = mockState();
    await installMockApi(page, state);
    await page.goto("/boards");
    await expect(page).toHaveURL(/\/boards$/);
    await expect(page.getByText("Личных досок пока нет")).toBeVisible();

    await page.getByRole("button", { name: "Новая доска" }).click();
    await expect(page.getByRole("tablist", { name: "Мои доски" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Доска 1" })).toHaveAttribute("aria-selected", "true");
    await expect(page).toHaveURL(/board=10/);
    expect(state.writes.find((write) => write.method === "POST" && write.path === "/boards")).toBeTruthy();

    const viewport = page.getByRole("region", { name: /Холст доски/ });
    const area = (await viewport.boundingBox())!;
    await page.keyboard.press("s");
    await page.mouse.click(area.x + 260, area.y + 220);
    await expect(page.getByText("Это личная доска без проекта, поэтому стикер нельзя связать с задачами.")).toBeVisible();
    await expect(page.getByRole("searchbox", { name: "Поиск задачи" })).toHaveCount(0);
    await page.getByPlaceholder("Что важно зафиксировать для команды?").fill("Схема склада");
    await page.getByRole("button", { name: "Добавить" }).click();
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(1);
    await expect.poll(() => state.writes.some(write => write.method === "POST" && write.path === "/boards/10/batch" && JSON.stringify(write.body).includes("create_sticker"))).toBe(true);

    // Сохранённое переживает перезагрузку.
    await page.reload();
    await expect(page.locator("[data-kind='sticker']")).toContainText("Схема склада");

    // Последнюю личную доску удалить можно — раздел снова пустой.
    await page.getByTitle("Переименовать или удалить эту доску").getByRole("button").click();
    await page.getByRole("button", { name: "Удалить доску" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Удалить доску" }).click();
    await expect(page.getByText("Личных досок пока нет")).toBeVisible();
    expect(state.errors).toEqual([]);
});

test("проектные доски не попадают в раздел «Доски»", async ({ page }) => {
    const state = mockState();
    await installMockApi(page, state);
    await page.goto("/boards");
    await expect(page.getByText("Личных досок пока нет")).toBeVisible();
    await expect(page.getByRole("tab", { name: "Основная" })).toHaveCount(0);
});
