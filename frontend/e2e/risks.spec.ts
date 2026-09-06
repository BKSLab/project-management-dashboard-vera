import { expect, test, type Page } from "@playwright/test";

const timestamp = "2026-09-06T10:00:00Z";
const user = { id: 1, username: "vera", first_name: "Вера", last_name: "Иванова", middle_name: null, is_active: true, has_avatar: false };
const project = { id: 1, key: "DEMO", name: "Интеграция CRM", description_md: "Запуск CRM", status: "ACTIVE", color: "#7299cc", icon: null, start_date: null, due_date: null, order_index: 0, created_at: timestamp, updated_at: timestamp };
const task = { id: 7, project_id: 1, stage_id: 1, key: "DEMO-142", number: 142, title: "Согласовать контракт API", description_md: "Ждём поставщика", priority: "HIGH", position: 1000, start_date: null, due_date: null, executor: null, participants: [], wbs_node_id: null, created_at: timestamp, updated_at: timestamp };
const baseRisk = { id: 12, key: "RISK-12", project_id: 1, title: "Задержка интеграции CRM", description: "Поставщик может задержать документацию.", probability: "HIGH", impact: "HIGH", risk_level: "HIGH", status: "OPEN", response_strategy: "MITIGATE", mitigation_plan: "Согласовать API заранее", response_plan: "Использовать резервный адаптер", owner_user_id: 1 as number | null, task_id: 7 as number | null, review_date: "2026-09-06" as string | null, source: "MANUAL", created_at: timestamp, updated_at: timestamp };
type Risk = typeof baseRisk;

async function mockProject(page: Page, risks: Risk[] = [{ ...baseRisk }]) {
    const state = { risks, fail: false, requests: [] as URL[], writes: [] as { method: string; body: Record<string, unknown> | null }[], errors: [] as string[] };
    page.on("pageerror", (error) => state.errors.push(error.message));
    await page.route("**/api/v1/**", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const path = url.pathname;
        const method = request.method();
        const headers = { "access-control-allow-origin": "http://127.0.0.1:4179", "access-control-allow-credentials": "true", "access-control-allow-headers": "content-type", "access-control-allow-methods": "GET, POST, PATCH, DELETE, OPTIONS" };
        const reply = (json: unknown, status = 200) => route.fulfill({ status, json, headers });
        if (method === "OPTIONS") return route.fulfill({ status: 204, headers });
        if (path.endsWith("/auth/me")) return reply(user);
        if (path === "/api/v1/projects") return reply([project]);
        if (path.endsWith("/stats")) return reply({ project_id: 1, total_tasks: 1, done_tasks: 0, in_progress_tasks: 1, overdue_tasks: 0, due_soon_tasks: 0, unassigned_tasks: 0, completion_rate: 0, next_due_date: null, stage_breakdown: [] });
        if (path.endsWith("/members")) return reply([{ id: 1, project_id: 1, role: "OWNER", user, created_at: timestamp }]);
        if (path.endsWith("/tasks")) return reply([task]);
        if (path === "/api/v1/tasks/7") return reply(task);
        if (path.endsWith("/risks/suggestions")) return reply({ suggestions: [{ title: "Зависимость от поставщика", description: "Не согласован контракт API", probability: "HIGH", impact: "MEDIUM", response_strategy: "MITIGATE", mitigation_plan: "Проверить контракт", response_plan: "Резервный адаптер", task_id: 7, evidence: ["DEMO-142: Ждём поставщика"] }] });
        if (path.includes("/risks")) {
            state.requests.push(url);
            const match = path.match(/\/risks\/(\d+)$/);
            if (method !== "GET") {
                const body = method === "DELETE" ? null : request.postDataJSON();
                state.writes.push({ method, body });
                if (method === "DELETE") {
                    state.risks = state.risks.filter((risk) => risk.id !== Number(match?.[1]));
                    return route.fulfill({ status: 204, headers });
                }
                const previous = method === "PATCH" ? state.risks.find((risk) => risk.id === Number(match?.[1]))! : { ...baseRisk, id: 100, key: "RISK-100" };
                const risk = { ...previous, ...body };
                risk.risk_level = risk.probability === "HIGH" && risk.impact !== "LOW" ? "HIGH" : "MEDIUM";
                state.risks = [...state.risks.filter((item) => item.id !== risk.id), risk];
                return reply(risk, method === "POST" ? 201 : 200);
            }
            if (match) return reply(state.risks.find((risk) => risk.id === Number(match[1])));
            const filtered = state.risks.filter((risk) => {
                if (url.searchParams.get("active_only") === "true" && risk.status === "CLOSED") return false;
                for (const key of ["probability", "impact", "status", "risk_level", "owner_user_id", "task_id"] as const) {
                    if (url.searchParams.has(key) && String(risk[key]) !== url.searchParams.get(key)) return false;
                }
                return `${risk.key} ${risk.title} ${risk.description}`.toLowerCase().includes((url.searchParams.get("search") ?? "").toLowerCase());
            });
            if (path.endsWith("/summary")) return reply({ total_risks: filtered.length, active_risks: filtered.filter((risk) => risk.status !== "CLOSED").length, high_risks: filtered.filter((risk) => risk.risk_level === "HIGH").length, occurred_risks: 0, risks_due_for_review: 0, signals: [], latest_update: timestamp, matrix: ["LOW", "MEDIUM", "HIGH"].flatMap((probability) => ["LOW", "MEDIUM", "HIGH"].map((impact) => ({ probability, impact, count: filtered.filter((risk) => risk.probability === probability && risk.impact === impact).length }))) });
            if (state.fail) return reply({ detail: "Ошибка чтения реестра" }, 500);
            const number = Number(url.searchParams.get("page") ?? 1);
            return reply({ total: filtered.length, page: number, page_size: 25, items: filtered.slice((number - 1) * 25, number * 25) });
        }
        return reply([]);
    });
    return state;
}

test("реестр показывает загрузку, пустое состояние, ошибку и повтор", async ({ page }) => {
    const state = await mockProject(page, []);
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/risks?*", async (route) => { await gate; await route.fallback(); }, { times: 1 });
    await page.goto("/projects/DEMO/risks");
    await expect(page.getByRole("status", { name: "Загрузка реестра рисков" })).toBeVisible();
    release();
    await expect(page.getByText("В проекте пока нет активных рисков", { exact: true })).toBeVisible();
    state.fail = true;
    await page.getByLabel("Поиск рисков").fill("API");
    await expect(page.getByText("Ошибка чтения реестра")).toBeVisible();
    state.fail = false;
    await page.getByRole("button", { name: "Повторить", exact: true }).click();
    await expect(page.getByText("Риски не найдены", { exact: true })).toBeVisible();
    expect(state.errors).toEqual([]);
});

test("создание, выбор связей, редактирование и подтверждение удаления", async ({ page }) => {
    const state = await mockProject(page, []);
    await page.goto("/projects/DEMO/risks");
    await page.getByRole("button", { name: "Добавить риск", exact: true }).click();
    const modal = page.getByRole("dialog", { name: "Новый риск" });
    await expect(modal.getByLabel("Название *", { exact: true })).toBeFocused();
    await modal.getByRole("button", { name: "Создать риск", exact: true }).click();
    expect(state.writes).toEqual([]);
    await modal.getByLabel("Название *", { exact: true }).fill("Задержка поставки");
    await modal.getByLabel("Описание *", { exact: true }).fill("Риск задержки документации");
    await modal.getByLabel("Вероятность *", { exact: true }).selectOption("HIGH");
    await modal.getByLabel("Влияние *", { exact: true }).selectOption("MEDIUM");
    await expect(modal.getByLabel("Уровень риска: Высокий")).toBeVisible();
    await modal.getByLabel("Ответственный", { exact: true }).selectOption("1");
    await modal.getByLabel("Поиск задачи проекта").fill("DEMO-142");
    await modal.getByLabel("Связанная задача", { exact: true }).selectOption("7");
    await modal.getByLabel("План митигации", { exact: true }).fill("Согласовать заранее");
    await modal.getByLabel("План реагирования", { exact: true }).fill("Резервный адаптер");
    await modal.getByRole("button", { name: "Создать риск", exact: true }).click();
    const drawer = page.getByRole("dialog", { name: "Риск RISK-100", exact: true });
    await expect(drawer).toBeVisible();
    expect(state.writes[0].body).toMatchObject({ task_id: 7, owner_user_id: 1, probability: "HIGH", impact: "MEDIUM" });
    expect(state.writes[0].body).not.toHaveProperty("risk_level");
    await drawer.getByRole("button", { name: "Редактировать", exact: true }).click();
    await drawer.getByLabel("Влияние *", { exact: true }).selectOption("LOW");
    await drawer.getByLabel("Связанная задача", { exact: true }).selectOption("");
    await drawer.getByRole("button", { name: "Сохранить", exact: true }).click();
    await expect(drawer.getByLabel("Уровень риска: Средний")).toBeVisible();
    expect(state.writes[1].body).toEqual({ impact: "LOW", task_id: null });
    await drawer.getByRole("button", { name: "Удалить", exact: true }).click();
    const confirmation = page.getByRole("dialog", { name: "Удалить RISK-100?" });
    await confirmation.getByRole("button", { name: "Отмена", exact: true }).click();
    expect(state.writes).toHaveLength(2);
    await expect(drawer.getByRole("button", { name: "Удалить", exact: true })).toBeFocused();
    await drawer.getByRole("button", { name: "Удалить", exact: true }).click();
    await confirmation.getByRole("button", { name: "Удалить риск", exact: true }).click();
    await expect(drawer).not.toBeVisible();
    expect(state.writes[2].method).toBe("DELETE");
    expect(state.errors).toEqual([]);
});

test("матрица считает весь набор, фильтрует с клавиатуры и сбрасывает страницу", async ({ page }, info) => {
    const state = await mockProject(page, Array.from({ length: 30 }, (_, index) => ({ ...baseRisk, id: index + 1, key: `RISK-${index + 1}` })));
    await page.goto("/projects/DEMO/risks");
    const cell = page.getByRole("button", { name: "Высокая вероятность, высокое влияние: 30" });
    await expect(cell).toBeVisible();
    await expect(page.getByRole("list", { name: "Реестр рисков" }).getByRole("listitem")).toHaveCount(25);
    await page.getByRole("button", { name: "Следующая страница рисков" }).click();
    await expect(page.getByRole("list", { name: "Реестр рисков" }).getByRole("listitem")).toHaveCount(5);
    await cell.focus();
    await page.keyboard.press("Enter");
    await expect(cell).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => state.requests.some((url) => url.searchParams.get("probability") === "HIGH" && url.searchParams.get("impact") === "HIGH" && url.searchParams.get("page") === "1")).toBe(true);
    await cell.press("Space");
    await expect(cell).toHaveAttribute("aria-pressed", "false");
    await page.screenshot({ path: info.outputPath("risks-desktop.png"), fullPage: true });
    expect(state.errors).toEqual([]);
});

test("AI-предложение можно отклонить или отредактировать перед отдельным созданием", async ({ page }) => {
    const state = await mockProject(page, []);
    await page.goto("/projects/DEMO/risks");
    await page.getByRole("button", { name: "Предложить риски", exact: true }).click();
    await expect(page.getByText("DEMO-142: Ждём поставщика")).toBeVisible();
    expect(state.writes).toEqual([]);
    await page.getByRole("button", { name: "Отклонить", exact: true }).click();
    expect(state.writes).toEqual([]);
    await page.getByRole("button", { name: "Предложить риски", exact: true }).click();
    await page.getByRole("button", { name: "Проверить и создать", exact: true }).click();
    const modal = page.getByRole("dialog", { name: "Новый риск" });
    await modal.getByLabel("Название *", { exact: true }).fill("Проверенный риск поставщика");
    expect(state.writes).toEqual([]);
    await modal.getByRole("button", { name: "Создать риск", exact: true }).click();
    await expect.poll(() => state.writes.length).toBe(1);
    expect(state.writes[0].body).toMatchObject({ source: "AI_SUGGESTED", title: "Проверенный риск поставщика" });
    expect(state.errors).toEqual([]);
});

test("узкий экран: реестр и Drawer помещаются, Escape возвращает фокус", async ({ page }, info) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const state = await mockProject(page);
    await page.goto("/projects/DEMO/risks");
    const row = page.getByRole("button", { name: "Открыть RISK-12: Задержка интеграции CRM" });
    await expect(row).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("risks-mobile.png"), fullPage: true });
    await row.click();
    const drawer = page.getByRole("dialog", { name: "Риск RISK-12", exact: true });
    await expect(drawer).toBeVisible();
    expect((await drawer.boundingBox())!.width).toBeLessThanOrEqual(390);
    await page.screenshot({ path: info.outputPath("risk-drawer-mobile.png"), fullPage: true });
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
    await expect(row).toBeFocused();
    expect(state.errors).toEqual([]);
});
