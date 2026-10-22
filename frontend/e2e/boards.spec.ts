import { expect, test, type Locator, type Page } from "@playwright/test";
import { installMockApi, mockState, type MockState } from "./support/mockApi";

/**
 * Доски проекта: несколько досок во вкладках и рисование (docs/boards-drawing.md).
 * Мок хранит состояние между запросами — перезагрузка страницы показывает сохранённое.
 */

async function center(locator: Locator): Promise<{ x: number; y: number }> {
    const box = await locator.boundingBox();
    if (!box) throw new Error("элемент не на экране");
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

async function drag(page: Page, from: { x: number; y: number }, to: { x: number; y: number }) {
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move(from.x + (to.x - from.x) / 3, from.y + (to.y - from.y) / 3, { steps: 4 });
    await page.mouse.move(to.x, to.y, { steps: 8 });
    await page.mouse.up();
}

/** Ждём, пока очередь сохранения отправит пакет (дебаунс 300 мс). */
async function waitSaved(page: Page, state: MockState, count: number) {
    await expect.poll(() => state.writes.filter((write) => write.path.endsWith("/batch")).length).toBeGreaterThanOrEqual(count);
    await expect(page.getByRole("status", { name: "Сохранение доски" })).toHaveText("Сохранено");
}

async function openBoard(page: Page, state: MockState, query = "") {
    await installMockApi(page, state);
    await page.goto(`/projects/DEMO/whiteboard${query}`);
    await expect(page.getByRole("tablist", { name: "Доски проекта" })).toBeVisible({ timeout: 60_000 });
}

test("новая доска: прямоугольник, стрелка от стикера, стрелка следует за стикером, всё сохраняется", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state);
    await page.getByRole("button", { name: "доска" }).click();
    await expect(page.getByRole("tab", { name: "Доска 3" })).toHaveAttribute("aria-selected", "true");
    await expect(page).toHaveURL(/board=10/);
    await expect(page.getByText("Выберите инструмент слева или нажмите S, чтобы поставить стикер")).toBeVisible();

    const viewport = page.getByRole("region", { name: /Холст доски/ });
    const area = (await viewport.boundingBox())!;

    // Стикер: клавиша S, клик по холсту, диалог
    await page.keyboard.press("s");
    await page.mouse.click(area.x + 260, area.y + 220);
    await page.getByPlaceholder("Что важно зафиксировать для команды?").fill("Клиент");
    await page.getByRole("button", { name: "Добавить" }).click();
    const sticker = page.locator("[data-kind='sticker']");
    await expect(sticker).toHaveCount(1);

    // Прямоугольник справа
    await page.getByRole("button", { name: "Прямоугольник (R)" }).click();
    await drag(page, { x: area.x + 620, y: area.y + 160 }, { x: area.x + 800, y: area.y + 280 });
    const rect = page.locator("[data-kind='rect']");
    await expect(rect).toHaveCount(1);
    await expect(page.getByRole("button", { name: "Выделение (V)" })).toHaveAttribute("aria-pressed", "true");

    // Стрелка: от стикера к прямоугольнику, концы прилипают
    await page.keyboard.press("a");
    await drag(page, await center(sticker), await center(rect));
    const arrow = page.locator("[data-kind='arrow']");
    await expect(arrow).toHaveCount(1);
    await waitSaved(page, state, 1);
    const created = state.shapes.find((shape) => shape.kind === "arrow")!;
    expect(created.start_ref).toMatchObject({ type: "sticker" });
    expect(created.end_ref).toMatchObject({ type: "shape", id: state.shapes.find((shape) => shape.kind === "rect")!.id });

    // Двигаем стикер вниз — стрелка следует
    const arrowBefore = (await arrow.boundingBox())!;
    const stickerCenter = await center(sticker);
    await page.keyboard.press("Escape");
    await drag(page, { x: stickerCenter.x, y: stickerCenter.y - 60 }, { x: stickerCenter.x, y: stickerCenter.y + 140 });
    const arrowAfter = (await arrow.boundingBox())!;
    expect(Math.abs(arrowAfter.height - arrowBefore.height) + Math.abs(arrowAfter.y - arrowBefore.y)).toBeGreaterThan(40);
    const stickerAfter = (await sticker.boundingBox())!;
    await waitSaved(page, state, 2);

    // Перезагрузка — всё на месте, стрелка прицеплена
    await page.reload();
    await expect(page.getByRole("tab", { name: "Доска 3" })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(1);
    await expect(page.locator("[data-kind='rect']")).toHaveCount(1);
    await expect(page.locator("[data-kind='arrow']")).toHaveCount(1);
    // Вид холста после перезагрузки другой — сравниваем положение стрелки относительно стикера.
    const reloaded = (await page.locator("[data-kind='arrow']").boundingBox())!;
    const stickerReloaded = (await page.locator("[data-kind='sticker']").boundingBox())!;
    expect(Math.abs((reloaded.y - stickerReloaded.y) - (arrowAfter.y - stickerAfter.y))).toBeLessThan(3);
    expect(Math.abs(reloaded.height - arrowAfter.height)).toBeLessThan(3);
    expect(state.errors).toEqual([]);
});

test("переключение досок через вкладки и ?board=", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state);
    await expect(page.getByRole("tab", { name: "Основная" })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(3);
    await page.getByRole("tab", { name: "Архитектура" }).click();
    await expect(page).toHaveURL(/board=2/);
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(0);
    await page.goto("/projects/DEMO/whiteboard?board=1");
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(3);

    // Переименование двойным кликом
    await page.getByRole("tab", { name: "Архитектура" }).dblclick();
    await page.getByLabel("Название доски").fill("Схема обмена");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("tab", { name: "Схема обмена" })).toBeVisible();
    expect(state.writes.some((write) => write.method === "PATCH" && write.path === "/projects/1/boards/2")).toBe(true);
});

test("«Заменить на стикер»: фигура становится стикером, стрелка остаётся прицеплена", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state);
    const viewport = page.getByRole("region", { name: /Холст доски/ });
    const area = (await viewport.boundingBox())!;

    await page.keyboard.press("r");
    await drag(page, { x: area.x + 400, y: area.y + 420 }, { x: area.x + 600, y: area.y + 520 });
    const rect = page.locator("[data-kind='rect']");
    await expect(rect).toHaveCount(1);

    const firstSticker = page.locator("[data-key='s1']");
    await page.keyboard.press("a");
    await drag(page, await center(firstSticker), await center(rect));
    await expect(page.locator("[data-kind='arrow']")).toHaveCount(1);

    await page.keyboard.press("Escape");
    await rect.click({ position: { x: 20, y: 20 } });
    await page.getByRole("button", { name: "Заменить на стикер" }).click();
    await expect(page.locator("[data-kind='rect']")).toHaveCount(0);
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(4);
    const arrow = state.shapes.find((shape) => shape.kind === "arrow")!;
    expect(arrow.end_ref).toMatchObject({ type: "sticker" });
    await expect.poll(() => state.writes.some(write => write.path.endsWith("/batch") && JSON.stringify(write.body).includes("create_sticker"))).toBe(true);
    await page.keyboard.press("Control+z");
    await expect(page.locator("[data-kind='rect']")).toHaveCount(1);
    await expect(page.locator("[data-kind='sticker']")).toHaveCount(3);
    expect(state.errors).toEqual([]);
});

test("отмена и повтор рисования, удаление с Delete", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state, "?board=2");
    const area = (await page.getByRole("region", { name: /Холст доски/ }).boundingBox())!;
    await page.keyboard.press("o");
    await drag(page, { x: area.x + 300, y: area.y + 200 }, { x: area.x + 420, y: area.y + 300 });
    await expect(page.locator("[data-kind='ellipse']")).toHaveCount(1);
    await page.keyboard.press("Control+z");
    await expect(page.locator("[data-kind='ellipse']")).toHaveCount(0);
    await page.keyboard.press("Control+Shift+z");
    await expect(page.locator("[data-kind='ellipse']")).toHaveCount(1);
    await page.keyboard.press("Control+d");
    await expect(page.locator("[data-kind='ellipse']")).toHaveCount(2);
    await page.keyboard.press("Delete");
    await expect(page.locator("[data-kind='ellipse']")).toHaveCount(1);
    await waitSaved(page, state, 1);
    await expect.poll(() => state.shapes.filter((shape) => shape.kind === "ellipse").length).toBe(1);
    expect(state.errors).toEqual([]);
});

test("подпись фигуры двойным кликом и свойства стрелки", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state, "?board=2");
    const area = (await page.getByRole("region", { name: /Холст доски/ }).boundingBox())!;
    await page.keyboard.press("r");
    await drag(page, { x: area.x + 300, y: area.y + 200 }, { x: area.x + 460, y: area.y + 300 });
    const rect = page.locator("[data-kind='rect']");
    await rect.dblclick({ position: { x: 40, y: 40 } });
    await page.getByLabel("Подпись фигуры").fill("Склад\nМосква");
    await page.keyboard.press("Control+Enter");
    await expect(rect).toContainText("Склад");

    await page.keyboard.press("a");
    await drag(page, { x: area.x + 600, y: area.y + 150 }, { x: area.x + 800, y: area.y + 350 });
    await page.getByRole("button", { name: "Ломаная под прямым углом" }).click();
    await page.getByRole("button", { name: "Обводка: Нейтральный" }).click();
    await page.getByRole("button", { name: "Обводка: Красный" }).click();
    await waitSaved(page, state, 1);
    await expect.poll(() => (state.shapes.find((shape) => shape.kind === "arrow")?.style as { route?: string } | undefined)?.route).toBe("orthogonal");
    const arrow = state.shapes.find((shape) => shape.kind === "arrow")!;
    expect((arrow.points as number[][]).length).toBeGreaterThan(2);
    expect((arrow.style as { stroke: string }).stroke).toBe("red");
    await expect.poll(() => state.shapes.find((shape) => shape.kind === "rect")?.label).toBe("Склад\nМосква");
    expect(state.errors).toEqual([]);
});

test("последнюю доску удалить нельзя, остальные — с подтверждением", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state, "?board=2");
    await page.getByRole("button", { name: "Действия с доской «Архитектура»" }).click();
    await page.getByRole("button", { name: "Удалить доску" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Удалить доску" }).click();
    await expect(page.getByRole("tab")).toHaveCount(1);
    await page.getByRole("button", { name: "Действия с доской «Основная»" }).click();
    await expect(page.getByRole("button", { name: "Удалить доску" })).toBeDisabled();
    await expect(page.getByText("Последнюю доску проекта удалить нельзя")).toBeVisible();
});

/** Относительная яркость по WCAG из rgb()/color(srgb …) — то, что браузер реально отрисовал. */
async function luminanceOf(locator: Locator, property: "backgroundColor" | "color" = "backgroundColor"): Promise<number> {
    return locator.evaluate((element, property) => {
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 1;
        const context = canvas.getContext("2d")!;
        context.fillStyle = getComputedStyle(element)[property];
        context.fillRect(0, 0, 1, 1);
        const [r, g, b] = context.getImageData(0, 0, 1, 1).data;
        const lin = (v: number) => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    }, property);
}

for (const theme of ["personal"] as const) {
    test(`свой цвет стикера: сохраняется hex, на доске — бумага темы (${theme})`, async ({ page }) => {
        const state = mockState();
        await openBoard(page, state);
        const card = page.locator("[data-kind='sticker']").first().locator(".project-sticker-card");
        await card.dblclick({ position: { x: 60, y: 40 } });
        const dialog = page.getByRole("dialog", { name: "Изменить стикер" });
        await expect(dialog.getByRole("button", { name: "Жёлтый" })).toHaveAttribute("aria-pressed", "true");
        await expect(dialog.getByTitle("Любой цвет: нажмите, чтобы открыть палитру")).toBeVisible();
        // Бордовый — самый тёмный цвет проектов: на светлой теме с тёмным текстом он нечитаем как есть.
        await dialog.getByLabel("Свой цвет стикера").fill("#7c1623");
        await expect(dialog.getByText("#7c1623")).toBeVisible();
        await expect(dialog.getByRole("button", { name: "Жёлтый" })).toHaveAttribute("aria-pressed", "false");
        await dialog.getByRole("button", { name: "Сохранить" }).click();
        await expect(dialog).toHaveCount(0);

        await expect.poll(() => state.stickers.find(item => item.id === 1)?.color).toBe("#7c1623");
        const luminance = await luminanceOf(card);
        const ink = await luminanceOf(card, "color");
        expect((Math.max(luminance, ink) + 0.05) / (Math.min(luminance, ink) + 0.05)).toBeGreaterThanOrEqual(4.5);
    });
}

/** BOARD_SHOTS=<папка> — снять доску со схемой в теме личного проекта и на телефоне. */
const BOARD_SHOTS = process.env.BOARD_SHOTS;

function seedDiagram(state: MockState) {
    const base = { board_id: 1, created_by_user_id: 1, revision: 1, created_at: "2026-09-28T10:00:00Z", updated_at: "2026-09-28T10:00:00Z", points: null, start_ref: null, end_ref: null };
    const style = (patch: Record<string, unknown> = {}) => ({ stroke: "neutral", fill: "none", stroke_width: 2, dash: "solid", route: "straight", start_head: "none", end_head: "none", font_size: "m", text_align: "center", ...patch });
    state.shapes.push(
        { ...base, id: 201, kind: "rect", x: 40, y: 360, w: 200, h: 96, z_index: 4, label: "Заявка клиента", style: style({ stroke: "blue", fill: "blue" }) },
        { ...base, id: 202, kind: "diamond", x: 340, y: 350, w: 180, h: 116, z_index: 5, label: "Есть остаток?", style: style({ stroke: "violet", fill: "violet" }) },
        { ...base, id: 203, kind: "ellipse", x: 620, y: 360, w: 180, h: 96, z_index: 6, label: "Отгрузка", style: style({ stroke: "green", fill: "green" }) },
        { ...base, id: 204, kind: "text", x: 350, y: 500, w: 220, h: 40, z_index: 7, label: "нет — заказ поставщику", style: style({ stroke: "none", font_size: "s" }) },
        { ...base, id: 205, kind: "arrow", x: 0, y: 0, w: 0, h: 0, z_index: 8, label: "", points: [[0, 0], [1, 1]], start_ref: { type: "shape", id: 201, anchor: "right" }, end_ref: { type: "shape", id: 202, anchor: "left" }, style: style({ end_head: "arrow" }) },
        { ...base, id: 206, kind: "arrow", x: 0, y: 0, w: 0, h: 0, z_index: 9, label: "да", points: [[0, 0], [1, 1]], start_ref: { type: "shape", id: 202, anchor: "right" }, end_ref: { type: "shape", id: 203, anchor: "left" }, style: style({ end_head: "arrow", stroke: "green" }) },
        { ...base, id: 207, kind: "arrow", x: 0, y: 0, w: 0, h: 0, z_index: 10, label: "", points: [[0, 0], [1, 1]], start_ref: { type: "sticker", id: 2, anchor: "bottom" }, end_ref: { type: "shape", id: 202, anchor: "top" }, style: style({ end_head: "arrow", route: "orthogonal", dash: "dashed", stroke: "red" }) },
    );
}

for (const theme of ["personal"] as const) {
    test(`скриншот доски со схемой — ${theme}`, async ({ page }) => {
        test.skip(!BOARD_SHOTS, "только по BOARD_SHOTS");
        const state = mockState();
        seedDiagram(state);
        await openBoard(page, state);
        await expect(page.locator("[data-kind='arrow']")).toHaveCount(3);
        await page.locator("[data-key='f202']").click({ position: { x: 30, y: 58 } });
        await expect(page.getByRole("toolbar", { name: "Свойства выделенного" })).toBeVisible();
        await page.screenshot({ path: `${BOARD_SHOTS}/boards-${theme}.png` });
        await page.getByRole("button", { name: "Горячие клавиши доски" }).click();
        await page.screenshot({ path: `${BOARD_SHOTS}/boards-${theme}-shortcuts.png` });
    });
}

test("скриншот доски на телефоне", async ({ page }) => {
    test.skip(!BOARD_SHOTS, "только по BOARD_SHOTS");
    const state = mockState();
    seedDiagram(state);
    await page.setViewportSize({ width: 390, height: 844 });
    await openBoard(page, state);
    await expect(page.locator("[data-kind='arrow']")).toHaveCount(3);
    await page.screenshot({ path: `${BOARD_SHOTS}/boards-phone.png` });
});

test("правая кнопка тянет холст и ничего не рисует, даже с инструментом фигуры", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state);
    const viewport = page.getByRole("region", { name: /Холст доски/ });
    const world = page.locator(".board-world");
    const area = (await viewport.boundingBox())!;
    const before = await world.evaluate((node) => (node as HTMLElement).style.transform);

    await page.getByRole("button", { name: "Прямоугольник (R)" }).click();
    await page.mouse.move(area.x + 300, area.y + 300);
    await page.mouse.down({ button: "right" });
    await page.mouse.move(area.x + 360, area.y + 340, { steps: 6 });
    await page.mouse.up({ button: "right" });

    const after = await world.evaluate((node) => (node as HTMLElement).style.transform);
    expect(after).not.toBe(before);
    await expect(page.locator("[data-kind='rect']")).toHaveCount(0);
});

test("колёсико мыши масштабирует холст у курсора, как в Miro", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state);
    const viewport = page.getByRole("region", { name: /Холст доски/ });
    const area = (await viewport.boundingBox())!;
    const zoomButton = page.getByRole("button", { name: /^Масштаб \d+%/ });
    const zoomOf = async () => Number((await zoomButton.textContent())!.replace("%", ""));
    const before = await zoomOf();

    await page.mouse.move(area.x + area.width / 2, area.y + area.height / 2);
    await page.mouse.wheel(0, -120);
    await expect.poll(zoomOf).toBeGreaterThan(before);
    const zoomedIn = await zoomOf();
    await page.mouse.wheel(0, 120);
    await page.mouse.wheel(0, 120);
    await expect.poll(zoomOf).toBeLessThan(zoomedIn);

    // Дробный шаг, как приходит через RDP и при масштабе экрана Windows, — тоже масштаб
    const zoomedOut = await zoomOf();
    await page.mouse.wheel(0, -83.33);
    await expect.poll(zoomOf).toBeGreaterThan(zoomedOut);
});

test("фигура — контейнер: текст внутри едет вместе с ней, с Ctrl — только фигура", async ({ page }) => {
    const state = mockState();
    await openBoard(page, state);
    await page.getByRole("button", { name: "доска" }).click();
    await expect(page.getByText("Выберите инструмент слева или нажмите S", { exact: false })).toBeVisible();
    const viewport = page.getByRole("region", { name: /Холст доски/ });
    const area = (await viewport.boundingBox())!;

    await page.getByRole("button", { name: "Прямоугольник (R)" }).click();
    await drag(page, { x: area.x + 200, y: area.y + 150 }, { x: area.x + 520, y: area.y + 380 });
    const rect = page.locator("[data-kind='rect']");
    await expect(rect).toHaveCount(1);

    await page.keyboard.press("t");
    await drag(page, { x: area.x + 260, y: area.y + 190 }, { x: area.x + 400, y: area.y + 230 });
    await page.getByLabel("Подпись фигуры").fill("Внутри");
    await page.keyboard.press("Control+Enter");
    const text = page.locator("[data-kind='text']");
    await expect(text).toHaveCount(1);
    await page.keyboard.press("Escape");

    const textBefore = (await text.boundingBox())!;
    const grab = { x: area.x + 460, y: area.y + 330 };
    await drag(page, grab, { x: grab.x + 150, y: grab.y + 100 });
    await expect.poll(async () => (await text.boundingBox())!.x - textBefore.x).toBeGreaterThan(120);
    const textMoved = (await text.boundingBox())!;
    expect(textMoved.y - textBefore.y).toBeGreaterThan(80);

    // С Ctrl тянется только сама фигура
    const rectBox = (await rect.boundingBox())!;
    const grab2 = { x: rectBox.x + rectBox.width - 40, y: rectBox.y + rectBox.height - 30 };
    await page.keyboard.down("Control");
    await drag(page, grab2, { x: grab2.x + 120, y: grab2.y });
    await page.keyboard.up("Control");
    await expect.poll(async () => (await rect.boundingBox())!.x - rectBox.x).toBeGreaterThan(100);
    const textStill = (await text.boundingBox())!;
    expect(Math.abs(textStill.x - textMoved.x)).toBeLessThan(2);
    expect(state.errors).toEqual([]);
});


for (const viewport of [{width: 1440, height: 1000}, {width: 390, height: 844}]) {
    test(`масштаб доступен над кнопками чата (${viewport.width}px)`, async ({page}) => {
        const state = mockState();
        await page.setViewportSize(viewport);
        await openBoard(page, state);
        await expect(page.locator("[data-kind='sticker']")).toHaveCount(3);
        const controls = page.getByRole("group", {name: "Масштаб холста"});
        await controls.getByRole("button", {name: "Увеличить масштаб"}).click();
        await expect(controls.getByRole("button", {name: /Масштаб 120%/})).toBeVisible();
        await controls.getByRole("button", {name: /Масштаб 120%/}).click();
        await expect(controls.getByRole("button", {name: /Масштаб 100%/})).toBeVisible();
        expect(state.errors).toEqual([]);
    });
}
