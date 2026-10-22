import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { installMockApi, mockState } from "./support/calendarMockApi";

test.setTimeout(60_000);

/**
 * Шкала проекта, строки по исполнителям: тепловая полоса загрузки по дням с учётом
 * других проектов (docs/calendar.md «Загрузка»). SHOTS_DIR=<папка> — скриншоты обеих тем.
 */
const SHOTS_DIR = process.env.SHOTS_DIR;
const iso = (offset: number) => {
    const date = new Date();
    date.setDate(date.getDate() + offset);
    return date.toISOString().slice(0, 10);
};

async function shot(page: Page, name: string) {
    if (!SHOTS_DIR) return;
    fs.mkdirSync(SHOTS_DIR, { recursive: true });
    await page.waitForTimeout(150);
    await page.screenshot({ path: path.join(SHOTS_DIR, `${name}.png`) });
}

test("строки по исполнителям: переключатель, перегруз и подсказка дня", async ({ page }) => {
    const state = mockState();
    await installMockApi(page, state);
    await page.goto(`/projects/DEMO/calendar?view=timeline&scale=month&date=${iso(0)}`);

    const switcher = page.getByRole("group", { name: "Строки шкалы по" });
    await expect(switcher.getByRole("button", { name: "ИСР" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("button", { name: /^1 Разработка/ })).toBeVisible();

    await switcher.getByRole("button", { name: "Исполнителям" }).click();
    await expect(page).toHaveURL(/group=assignee/);
    await expect(page.getByTestId("workload-legend")).toContainText("перегруз");

    // Строка-заголовок на человека со сводкой в подсказке.
    const anna = page.getByRole("button", { name: /^Иванова Анна/ });
    await expect(anna).toBeVisible();
    await expect(anna).toHaveAttribute("title", /В периоде: \d+ задач/);

    // Перегруз подсвечен: у Анны на этой неделе задачи ещё и в другом проекте.
    const strip = page.getByRole("list", { name: "Загрузка: Иванова Анна" });
    const overloaded = strip.locator('[data-level="3"]').first();
    await expect(overloaded).toBeVisible();
    await expect(overloaded.locator("[data-workload-other]")).toBeVisible();
    const hint = await overloaded.getAttribute("title");
    expect(hint).toMatch(/^\d{4}-\d{2}-\d{2}: \d+ задач[аи]? — перегруз/);
    expect(hint).toContain("В других проектах: WMS-7, 1 без доступа к проекту");

    // Выбор запоминается: без ?group в адресе снова по исполнителям.
    await page.goto(`/projects/DEMO/calendar?view=timeline&scale=month&date=${iso(0)}`);
    await expect(page.getByRole("group", { name: "Строки шкалы по" }).getByRole("button", { name: "Исполнителям" })).toHaveAttribute("aria-pressed", "true");
    await shot(page, "gantt-workload-1440-light");

    await page.getByRole("group", { name: "Строки шкалы по" }).getByRole("button", { name: "Стадиям" }).click();
    await expect(page).toHaveURL(/group=stage/);
    await expect(page.getByText("Бэклог")).toBeVisible();
    expect(state.errors).toEqual([]);
});

if (SHOTS_DIR) {
    test("скриншот загрузки в тёмной теме", async ({ page }) => {
        await page.emulateMedia({ colorScheme: "dark" });
        await installMockApi(page, mockState());
        await page.goto(`/projects/DEMO/calendar?view=timeline&scale=month&date=${iso(0)}&group=assignee`);
        await expect(page.getByRole("list", { name: "Загрузка: Иванова Анна" })).toBeVisible();
        await page.waitForLoadState("networkidle");
        await shot(page, "gantt-workload-1440-dark");
    });
}
