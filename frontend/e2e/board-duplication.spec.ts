import { expect, test } from "@playwright/test";
import { installMockApi, mockState } from "./support/mockApi";

for (const personal of [false, true]) {
    test(`дублирование и полная отмена стикеров: ${personal ? "личная" : "проектная"} доска`, async ({page}) => {
        const state = mockState();
        if (personal) {
            state.boards.push({...state.boards[0], id: 10, project_id: null, title: "Личная", revision: 1, position: 0, created_by_user_id: 1});
            state.stickers.push({...state.stickers[0], id: 50, board_id: 10, project_id: null});
            state.nextIds.sticker = 51;
        }
        await installMockApi(page, state);
        await page.goto(personal ? "/boards?board=10" : "/projects/DEMO/whiteboard");
        const count = personal ? 1 : 3;
        await expect(page.locator("[data-kind='sticker']")).toHaveCount(count);
        await page.locator("[data-kind='sticker']").first().click({position: {x: 20, y: 20}});
        await page.getByRole("button", {name: "Дублировать выделенное"}).click();
        await expect(page.locator("[data-kind='sticker']")).toHaveCount(count + 1);
        await expect.poll(() => state.stickers.filter(item => item.board_id === (personal ? 10 : 1)).length).toBe(count + 1);
        await page.keyboard.press("Control+z");
        await expect(page.locator("[data-kind='sticker']")).toHaveCount(count);
        await expect.poll(() => state.stickers.filter(item => item.board_id === (personal ? 10 : 1)).length).toBe(count);
        await page.keyboard.press("Control+Shift+z");
        await expect(page.locator("[data-kind='sticker']")).toHaveCount(count + 1);
        await expect.poll(() => state.stickers.filter(item => item.board_id === (personal ? 10 : 1)).length).toBe(count + 1);
        await page.reload();
        await expect(page.locator("[data-kind='sticker']")).toHaveCount(count + 1);
        expect(state.errors).toEqual([]);
    });
}

test("изменение агентом видно без перезагрузки и отменяется одним действием", async ({page}) => {
    const state = mockState();
    await installMockApi(page, state);
    await page.goto("/projects/DEMO/whiteboard");
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(3);
    state.stickers.push({...state.stickers[0], id: 50, body: "Создано агентом", canvas_x: 600});
    state.nextIds.sticker = 51;
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(4, {timeout: 12000});
    await page.keyboard.press("Control+z");
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(3);
    await expect.poll(() => state.stickers.some(item => item.id === 50)).toBe(false);
    expect(state.errors).toEqual([]);
});

test("можно редактировать копию до получения её серверного id", async ({page}) => {
    const state = mockState();
    await installMockApi(page, state);
    await page.route("**/api/v1/projects/1/boards/1/batch", async route => {
        const body = route.request().postDataJSON();
        if (body.ops.some((op: {op: string}) => op.op === "create_sticker")) await new Promise(resolve => setTimeout(resolve, 1200));
        await route.fallback();
    });
    await page.goto("/projects/DEMO/whiteboard");
    await page.locator("[data-kind='sticker']").first().click({position: {x: 20, y: 20}});
    await page.getByRole("button", {name: "Дублировать выделенное"}).click();
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(4);
    await page.locator("[data-kind='sticker']").last().dblclick({position: {x: 20, y: 20}});
    await page.getByPlaceholder("Что важно зафиксировать для команды?").fill("Изменена до сохранения копии");
    await page.getByRole("dialog").getByRole("button", {name: "Сохранить"}).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect.poll(() => state.stickers.some(item => item.body === "Изменена до сохранения копии")).toBe(true);
    expect(state.errors).toEqual([]);
});

test("восстановленный стикер редактируется до завершения восстановления", async ({page}) => {
    const state = mockState();
    await installMockApi(page, state);
    await page.goto("/projects/DEMO/whiteboard");
    await page.locator("[data-key='s1']").click({position: {x: 20, y: 20}});
    await page.getByRole("button", {name: "Удалить выделенное"}).click();
    await expect(page.getByText("Удаление можно отменить через Ctrl+Z.")).toBeVisible();
    await page.getByRole("dialog").getByRole("button", {name: "Удалить", exact: true}).click();
    await expect.poll(() => state.stickers.length).toBe(2);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.route("**/api/v1/projects/1/boards/1/batch", async route => {
        if (route.request().postDataJSON().ops.some((op: {op: string}) => op.op === "create_sticker")) await new Promise(resolve => setTimeout(resolve, 1200));
        await route.fallback();
    });
    await page.keyboard.press("Control+z");
    await expect(page.locator("[data-key='s1']")).toBeVisible();
    await page.locator("[data-key='s1']").dblclick({position: {x: 20, y: 20}});
    await page.getByPlaceholder("Что важно зафиксировать для команды?").fill("Восстановлен и изменён");
    await page.getByRole("dialog").getByRole("button", {name: "Сохранить"}).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect.poll(() => state.stickers.some(item => item.body === "Восстановлен и изменён" && item.id !== 1)).toBe(true);
    expect(state.errors).toEqual([]);
});
