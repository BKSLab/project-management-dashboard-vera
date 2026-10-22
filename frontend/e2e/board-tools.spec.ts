import {expect, test} from "@playwright/test";
import {installMockApi, mockState} from "./support/mockApi";

async function open(page: import("@playwright/test").Page) {
    const state = mockState();
    await installMockApi(page, state);
    await page.goto("/projects/DEMO/whiteboard");
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(3);
    return state;
}
async function selectAll(page: import("@playwright/test").Page) {
    await page.locator("[data-kind='sticker']").first().click({position: {x: 20, y: 20}});
    await page.keyboard.press("Control+a");
}

test("выравнивание, явная группа и блокировка сохраняются и отменяются", async ({page}) => {
    const state = await open(page);
    await selectAll(page);
    await page.getByRole("button", {name: "Инструменты доски", exact: true}).click();
    await page.getByRole("button", {name: "По верхнему краю", exact: true}).click();
    await expect.poll(() => new Set(state.stickers.map(item => item.canvas_y)).size).toBe(1);
    await page.getByLabel("Название группы или шаблона").fill("План");
    await page.getByRole("button", {name: "Сгруппировать", exact: true}).click();
    await expect.poll(() => state.boards[0].editor_metadata?.groups.length).toBe(1);
    await expect(page.locator(".board-group-label")).toHaveText("План");
    await page.getByRole("button", {name: "Заблокировать", exact: true}).click();
    await expect.poll(() => state.boards[0].editor_metadata?.locked.length).toBe(3);
    await page.reload();
    await expect(page.locator("[data-kind='sticker'][data-locked]")).toHaveCount(3);
    const x = Number(state.stickers[0].canvas_x);
    await page.locator("[data-kind='sticker']").first().click({position: {x:20,y:20}});
    await page.keyboard.press("ArrowRight");
    expect(state.stickers[0].canvas_x).toBe(x);
    await page.getByRole("button", {name: "Инструменты доски", exact: true}).click();
    await page.getByRole("button", {name: "Разблокировать", exact: true}).click();
    await expect.poll(() => state.boards[0].editor_metadata?.locked.length).toBe(0);
    await page.keyboard.press("Control+z");
    await expect.poll(() => state.boards[0].editor_metadata?.locked.length).toBe(3);
    expect(state.errors).toEqual([]);
});

test("шаблон вставляется с группой и отменяется целиком", async ({page}) => {
    const state = await open(page);
    await selectAll(page);
    await page.getByRole("button", {name: "Инструменты доски", exact: true}).click();
    await page.getByLabel("Название группы или шаблона").fill("Блок");
    await page.getByRole("button", {name: "Сгруппировать", exact: true}).click();
    await expect.poll(() => state.boards[0].editor_metadata?.groups.length).toBe(1);
    await page.getByRole("button", {name: "Сохранить выделение как шаблон", exact: true}).click();
    await expect.poll(() => state.boards[0].editor_metadata?.templates.length).toBe(1);
    await page.getByLabel("Шаблон доски", {exact: true}).selectOption({label: "Блок"});
    await page.getByRole("button", {name: "Вставить шаблон", exact: true}).click();
    await expect.poll(() => state.stickers.length).toBe(6);
    await expect.poll(() => state.boards[0].editor_metadata?.groups.length).toBe(2);
    await page.keyboard.press("Control+z");
    await expect.poll(() => state.stickers.length).toBe(3);
    await expect.poll(() => state.boards[0].editor_metadata?.groups.length).toBe(1);
    await page.keyboard.press("Control+Shift+z");
    await expect.poll(() => state.stickers.length).toBe(6);
    await expect.poll(() => state.boards[0].editor_metadata?.groups.length).toBe(2);
    expect(state.errors).toEqual([]);
});

test("экспорт доски SVG и PNG создаёт скачиваемые файлы", async ({page}) => {
    await open(page);
    await page.getByRole("button", {name: "Инструменты доски", exact: true}).click();
    for (const format of ["SVG", "PNG"]) {
        const pending = page.waitForEvent("download");
        await page.getByRole("button", {name: "Выгрузить " + format, exact: true}).click();
        const download = await pending;
        expect(download.suggestedFilename()).toMatch(new RegExp("\\." + format.toLowerCase() + "$"));
        expect(await download.failure()).toBeNull();
    }
});

test("личная доска становится доской проекта без копий объектов", async ({page}) => {
    const state = mockState();
    state.boards.push({...state.boards[0], id: 10, project_id: null, title: "Идеи"});
    state.stickers.push({...state.stickers[0], id: 50, board_id: 10, project_id: null, task_ids: []});
    await installMockApi(page, state);
    await page.goto("/boards?board=10");
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(1);
    await page.getByRole("button", {name: "Инструменты доски", exact: true}).click();
    await page.getByRole("button", {name: "Создать проект из доски", exact: true}).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Код", {exact: true}).fill("IDEAS");
    await dialog.getByRole("button", {name: "Создать проект", exact: true}).click();
    await expect(page).toHaveURL(/projects\/IDEAS\/whiteboard\?board=10/);
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(1);
    expect(state.stickers.find(item => item.id === 50)?.board_id).toBe(10);
    expect(state.boards.find(item => item.id === 10)?.project_id).toBe(4);
});

test("polling не смешивает старые объекты с новыми группами и блокировками", async ({page}) => {
    const state = await open(page);
    let armed = true;
    let release = () => {};
    const changed = new Promise<void>(resolve => { release = resolve; });
    await page.route("**/api/v1/projects/1/boards/1/content", async route => {
        if (!armed) { await route.fallback(); return; }
        armed = false;
        const old = structuredClone({board: state.boards[0], stickers: state.stickers, shapes: state.shapes});
        state.stickers.push(
            {...state.stickers[0], id: 50, canvas_x: 600},
            {...state.stickers[0], id: 51, canvas_x: 900},
        );
        state.nextIds.sticker = 52;
        state.boards[0].revision = 2;
        state.boards[0].editor_metadata = {
            version: 1, groups: [{id: "remote", name: "Новая группа", members: [{type:"sticker",id:50},{type:"sticker",id:51}]}],
            locked: [{type:"sticker",id:50},{type:"sticker",id:51}], templates: [],
        };
        release();
        await route.fulfill({json: old});
    });
    await page.route("**/api/v1/projects/1/boards/1/editor-metadata", async route => {
        if (route.request().method() === "GET") await changed;
        await route.fallback();
    });
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(5, {timeout:12000});
    await expect(page.locator(".board-group-label")).toContainText("Новая группа");
    await expect(page.locator("[data-kind='sticker'][data-locked]")).toHaveCount(2);
    await page.locator("[data-key='s1']").click({position:{x:20,y:20}});
    await page.locator("[data-key='s2']").click({position:{x:20,y:20},modifiers:["Shift"]});
    await page.getByRole("button",{name:"Инструменты доски",exact:true}).click();
    await page.getByLabel("Название группы или шаблона").fill("Местная группа");
    await page.getByRole("button",{name:"Сгруппировать",exact:true}).click();
    await expect.poll(() => state.boards[0].editor_metadata?.groups.length).toBe(2);
    expect(state.boards[0].editor_metadata?.locked).toHaveLength(2);
});
