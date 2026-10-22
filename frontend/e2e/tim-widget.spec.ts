import { expect, test, type Page } from "@playwright/test";
import { installMockApi, mockState, type MockState } from "./support/mockApi";

test.setTimeout(60_000);

async function openTim(page: Page) {
    await page.getByRole("button", { name: "Спросить Веру", exact: true }).click();
    const panel = page.getByRole("dialog", { name: "Вера — проектный менеджер" });
    await expect(panel).toBeVisible();
    return panel;
}

async function setup(page: Page, patch: (state: MockState) => void = () => undefined) {
    const state = mockState();
    patch(state);
    await installMockApi(page, state);
    return state;
}

test("виджет видит страницу и открытую задачу, вопрос уходит с контекстом страницы", async ({ page }) => {
    const state = await setup(page);
    await page.goto("/projects/DEMO/tasks");
    await page.getByText("Согласовать макеты личного кабинета").first().click();
    await expect(page.getByRole("dialog", { name: "Задача DEMO-1", exact: true })).toBeVisible();
    // Кнопка Веры доступна поверх открытой карточки задачи
    const panel = await openTim(page);
    await expect(panel.getByTestId("tim-context")).toHaveText("Проект DEMO · задача DEMO-1");
    await expect(page.getByRole("dialog", { name: "Задача DEMO-1", exact: true })).toBeVisible();
    const input = panel.getByRole("textbox", { name: "Вопрос Вере" });
    await input.fill("Что с этой задачей?");
    await input.press("Enter");
    await expect(panel.getByText("По задачам всё в порядке: просрочек нет.")).toBeVisible();
    await expect(panel.getByText("Проект DEMO · задача #100", { exact: true })).toBeVisible();
    expect(state.tim.submissions).toHaveLength(1);
    expect(Object.keys(state.tim.submissions[0]).sort()).toEqual(["content", "file_ids", "page_context", "request_id"]);
    expect(state.tim.submissions[0].page_context).toEqual({ route: "/projects/DEMO/tasks", project_key: "DEMO", task_id: 100 });
    // Карточка задачи всё ещё открыта: клик в виджете её не закрыл
    await expect(page.getByRole("dialog", { name: "Задача DEMO-1", exact: true })).toBeVisible();
    await page.screenshot({ path: "test-results/tim-widget-task.png" });
    await panel.getByRole("textbox", { name: "Вопрос Вере" }).press("Escape");
    await expect(panel).toHaveCount(0);
    expect(state.errors).toEqual([]);
});

test("без проекта на странице Вера в личном режиме; ожидание ответа переживает перезагрузку", async ({ page }) => {
    const state = await setup(page, (value) => { value.tim.pending = true; });
    await page.goto("/projects");
    let panel = await openTim(page);
    await expect(panel.getByTestId("tim-context")).toHaveText("Личный помощник: ваши задачи и проекты");
    await panel.getByRole("textbox", { name: "Вопрос Вере" }).fill("Что у меня горит?");
    await panel.getByRole("button", { name: "Отправить Вере (Enter)" }).click();
    await expect(panel.getByText("Вера думает…")).toBeVisible();
    await page.goto("/");
    panel = await openTim(page);
    await expect(panel.getByTestId("tim-context")).toHaveText("Личный помощник: ваши задачи и проекты");
    await expect(panel.getByText("Вера думает…")).toBeVisible();
    // Живой статус вместо «думает»: что Вера делает прямо сейчас (опрос каждые 1,5 с).
    state.tim.progress = "Ищу среди ваших задач: «горит»…";
    const live = panel.getByRole("status");
    await expect(live).toHaveText("Ищу среди ваших задач: «горит»…");
    await expect(live).toHaveAttribute("aria-live", "polite");
    await expect(panel.getByText("Вера думает…")).toHaveCount(0);
    await page.screenshot({ path: "test-results/tim-widget-progress.png", animations: "disabled" });
    state.tim.pending = false;
    await expect(panel.getByText("По задачам всё в порядке: просрочек нет.")).toBeVisible();
    await expect(panel.getByText("Ищу среди ваших задач: «горит»…")).toHaveCount(0);
    expect(state.tim.submissions[0].page_context).toEqual({ route: "/projects", project_key: null, task_id: null });
});

test("новый диалог и возврат к прежнему; ошибка ответа — повтор без дубля вопроса", async ({ page }) => {
    const state = await setup(page);
    await page.goto("/projects");
    const panel = await openTim(page);
    const input = panel.getByRole("textbox", { name: "Вопрос Вере" });
    await input.fill("Обсудим тестирование окна заказа");
    await input.press("Enter");
    await expect(panel.getByText("По задачам всё в порядке: просрочек нет.")).toBeVisible();
    await panel.getByRole("button", { name: "Новый диалог с Верой — прежние останутся в списке" }).click();
    // Прежний вопрос остался только названием диалога в списке, в переписке его нет
    await expect(panel.locator("p", { hasText: "Обсудим тестирование окна заказа" })).toHaveCount(0);
    state.tim.fail = true;
    await input.fill("Расскажи о проекте");
    await input.press("Enter");
    await expect(panel.getByRole("button", { name: "Повторить", exact: true })).toBeVisible();
    state.tim.fail = false;
    await panel.getByRole("button", { name: "Повторить", exact: true }).click();
    await expect(panel.getByText("По задачам всё в порядке: просрочек нет.")).toBeVisible();
    await expect(panel.locator("p", { hasText: "Расскажи о проекте" })).toHaveCount(1);
    await panel.getByRole("combobox", { name: "Диалог с Верой" }).selectOption("1");
    await expect(panel.locator("p", { hasText: "Обсудим тестирование окна заказа" })).toBeVisible();
    expect(state.tim.submissions).toHaveLength(2);
});

for (const decision of ["approve", "reject"] as const) {
    test(`карточка действия в виджете: ${decision}`, async ({ page }) => {
        const state = await setup(page, (value) => {
            value.tim.action = { id: "5eea642e-3196-45c0-ac85-1286b0d3a81c", tool_name: "delete_task", title: "Удалить задачу",
                arguments: { task_id: 100, expected_updated_at: "2026-09-21T10:00:00Z" }, status: "pending",
                result: { preview: { task: { key: "DEMO-1", title: "Согласовать макеты" } } }, created_at: "2026-09-21T10:00:00Z" };
        });
        await page.goto("/projects/DEMO");
        const panel = await openTim(page);
        await panel.getByRole("textbox", { name: "Вопрос Вере" }).fill("Удали задачу DEMO-1");
        await panel.getByRole("textbox", { name: "Вопрос Вере" }).press("Enter");
        const card = panel.getByRole("region", { name: "Действие: Удалить задачу" });
        await expect(card.getByText("Ожидает решения", { exact: true })).toBeVisible();
        await card.getByRole("button", { name: decision === "approve" ? "Подтвердить" : "Отклонить", exact: true }).click();
        await expect(card.getByText(decision === "approve" ? "Выполнено" : "Отклонено", { exact: true })).toBeVisible();
        await expect(card.getByRole("button", { name: "Подтвердить", exact: true })).toHaveCount(0);
        expect(state.tim.decisions).toEqual([{ decision }]);
    });
}

test("файл уходит вместе с вопросом", async ({ page }) => {
    const state = await setup(page);
    await page.goto("/my-tasks");
    const panel = await openTim(page);
    await panel.getByLabel("Файлы для Веры").setInputFiles({ name: "acceptance.md", mimeType: "text/markdown", buffer: Buffer.from("Проверка окна") });
    await expect(panel.getByRole("button", { name: "Убрать acceptance.md" })).toBeVisible();
    await panel.getByRole("textbox", { name: "Вопрос Вере" }).fill("Посмотри файл");
    await panel.getByRole("textbox", { name: "Вопрос Вере" }).press("Enter");
    await expect(panel.getByRole("button", { name: "Убрать acceptance.md" })).toHaveCount(0);
    await expect(panel.locator("p", { hasText: "acceptance.md" })).toBeVisible();
    expect(state.tim.submissions[0].file_ids).toEqual(["f918d205-2ced-48eb-85f4-19b8e55ef361"]);
});

test("на телефоне панель во весь экран; проект использует единый чат", async ({ page }) => {
    await setup(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/projects/DEMO");
    await expect(page.getByRole("link", { name: "Чат", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Агент", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Открыть чат агента" })).toHaveCount(0);
    const dock = page.getByLabel("Быстрый доступ к чатам", { exact: true });
    await expect(dock).toBeVisible();
    const dockBox = await dock.boundingBox();
    const buttonBox = await page.getByRole("button", { name: "Спросить Веру", exact: true }).boundingBox();
    expect(buttonBox!.y + buttonBox!.height).toBeLessThanOrEqual(dockBox!.y);
    const panel = await openTim(page);
    const box = await panel.boundingBox();
    expect(box).toEqual({ x: 0, y: 0, width: 390, height: 844 });
    await expect(panel.getByRole("button", { name: "Закрыть окно Веры" })).toBeInViewport();
    await expect(panel.getByRole("textbox", { name: "Вопрос Вере" })).toBeInViewport();
    await page.screenshot({ path: "test-results/tim-widget-mobile.png" });
    await panel.getByRole("button", { name: "Закрыть окно Веры" }).click();
    await expect(panel).toHaveCount(0);
    await page.goto("/projects/DEMO/agent");
    await expect(page).toHaveURL(/\/projects\/DEMO\/chat\?view=personal$/);
});
