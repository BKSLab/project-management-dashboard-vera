// @vitest-environment node
import { existsSync } from "node:fs";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { chromium, type Browser } from "@playwright/test";
import { createServer, type ViteDevServer } from "vite";

let browser: Browser;
let server: ViteDevServer;
let origin: string;

const browserChannel = process.env.PLAYWRIGHT_CHANNEL;
const browserAvailable = Boolean(browserChannel) || existsSync(chromium.executablePath());

beforeAll(async () => {
    if (!browserAvailable) return;
    server = await createServer({ server: { port: 0, host: "127.0.0.1", strictPort: false }, logLevel: "error" });
    await server.listen();
    const address = server.httpServer!.address();
    if (!address || typeof address === "string") throw new Error("Не удалось поднять локальный Vite.");
    origin = "http://127.0.0.1:" + address.port;
    browser = await chromium.launch({ headless: true, ...(browserChannel ? { channel: browserChannel } : {}) });
}, 30_000);
afterAll(async () => { await browser?.close(); await server?.close(); });

describe.skipIf(!browserAvailable)("автономный экспорт в настоящем Chromium", () => {
    it("PNG загружается, имеет нужные размеры/непустые пиксели и не обращается к внешним assets", async () => {
        const page = await browser.newPage();
        const external: string[] = [];
        page.on("request", (request) => { if (!request.url().startsWith(origin)) external.push(request.url()); });
        await page.route("**/export-smoke", (route) => route.fulfill({ contentType: "text/html", body: '<div id="root"></div>' }));
        await page.goto(origin + "/export-smoke");
        const result = await page.evaluate(async () => {
            const modulePath = "/src/lib/board/export.ts";
            const typePath = "/src/lib/board/types.ts";
            // Строковый dynamic import выполняется в браузере, не через Vitest SSR helper.
            const load = new Function("path", "return import(path)");
            const { exportSVG, exportPNG } = await load(modulePath);
            const { defaultStyle } = await load(typePath);
            const kinds = ["rect", "ellipse", "diamond", "text", "line", "arrow"];
            const objects = kinds.map((kind, index) => ({
                key: kind, type: "shape", kind, x: index * 120, y: 0, w: 100, h: 100, z: index,
                points: null, startRef: null, endRef: null, style: defaultStyle(kind, { fill: "blue", stroke: "red" }), label: "Текст " + kind,
            }));
            const scene = new Map(objects.map((object) => [object.key, object]));
            const svg = exportSVG(scene);
            const png = await exportPNG(scene, { scale: 1 });
            const bitmap = await createImageBitmap(png.blob);
            const canvas = document.createElement("canvas");
            canvas.width = png.width; canvas.height = png.height;
            const context = canvas.getContext("2d")!;
            context.drawImage(bitmap, 0, 0);
            const pixels = context.getImageData(0, 0, png.width, png.height).data;
            let coloured = 0;
            for (let index = 0; index < pixels.length; index += 4) {
                if (pixels[index + 3] && (pixels[index] !== 255 || pixels[index + 1] !== 255 || pixels[index + 2] !== 255)) coloured++;
            }
            bitmap.close();
            return { mime: png.blob.type, bytes: png.blob.size, width: png.width, height: png.height, svgWidth: svg.width, svgHeight: svg.height, coloured };
        });
        expect(result.mime).toBe("image/png");
        expect(result.bytes).toBeGreaterThan(100);
        expect(result.width).toBe(result.svgWidth);
        expect(result.height).toBe(result.svgHeight);
        expect(result.coloured).toBeGreaterThan(1000);
        expect(external).toEqual([]);
        await page.close();
    }, 30_000);

    it("CSS vars и OKLCH стикер дают автономные цвета светлой/тёмной темы; огромная доска ограничена", async () => {
        const page = await browser.newPage();
        await page.route("**/export-smoke", (route) => route.fulfill({ contentType: "text/html", body: '<div id="root"></div>' }));
        await page.goto(origin + "/export-smoke");
        const result = await page.evaluate(async () => {
            const modulePath = "/src/lib/board/export.ts";
            const typePath = "/src/lib/board/types.ts";
            const load = new Function("path", "return import(path)");
            const { resolveExportPalette, exportSVG, exportPNG } = await load(modulePath);
            const { defaultStyle } = await load(typePath);
            const root = document.getElementById("root")!;
            const configure = (dark: boolean) => {
                for (const color of ["neutral", "yellow", "blue", "green", "red", "violet"]) {
                    root.style.setProperty("--board-stroke-" + color, dark ? "#f4f4f5" : "#18181b");
                    root.style.setProperty("--board-fill-" + color, dark ? "#1c2f3a" : "#c9edff");
                }
                root.style.setProperty("--color-text-primary", dark ? "#f4f4f5" : "#18181b");
                root.style.setProperty("--color-bg-surface", dark ? "#191c23" : "#ffffff");
                root.style.setProperty("--color-bg-surface-2", dark ? "#20242d" : "#f5f5f7");
                root.style.setProperty("--surface-note-ink", dark ? "#f2eee5" : "#27241d");
                root.style.setProperty("--surface-note-border", "#aabbcc");
                root.style.setProperty("--note-l-min", dark ? "0.25" : "0.92");
                root.style.setProperty("--note-l-max", dark ? "0.32" : "0.97");
                root.style.setProperty("--note-c-max", "0.08");
            };
            configure(false);
            const light = resolveExportPalette(root);
            configure(true);
            const dark = resolveExportPalette(root);
            const sticker = {
                key: "s1", type: "sticker", id: 1, x: 0, y: 0, w: 160, h: 160, z: 1,
                sticker: { body: "Карточка", color: "#ff0000", title: "Заголовок", status: "Готово" },
            };
            const huge = {
                key: "huge", type: "shape", kind: "rect", x: 900_000, y: 0, w: 100, h: 100, z: 0,
                points: null, startRef: null, endRef: null, style: defaultStyle("rect"), label: "",
            };
            const scene = new Map<string, typeof sticker | typeof huge>([[sticker.key, sticker], [huge.key, huge]]);
            const svg = exportSVG(scene, { palette: dark });
            const png = await exportPNG(scene, { palette: dark, maxDimension: 512, maxPixels: 20_000 });
            const bitmap = await createImageBitmap(png.blob);
            const decoded = { width: bitmap.width, height: bitmap.height };
            bitmap.close();
            const parsed = new DOMParser().parseFromString(svg.svg, "image/svg+xml");
            return {
                light: light.text, dark: dark.text,
                fill: parsed.querySelector('[data-key="s1"] > rect')!.getAttribute("fill"),
                noVars: !svg.svg.includes("var("), probeCount: root.children.length,
                width: png.width, height: png.height, decoded,
            };
        });
        expect(result.light).toBe("rgb(24, 24, 27)");
        expect(result.dark).toBe("rgb(244, 244, 245)");
        expect(result.fill).toMatch(/^rgba?\(/);
        expect(result.noVars).toBe(true);
        expect(result.probeCount).toBe(0);
        expect(result.width).toBeLessThanOrEqual(512);
        expect(result.width * result.height).toBeLessThanOrEqual(20_000);
        expect(result.decoded).toEqual({ width: result.width, height: result.height });
        await page.close();
    }, 30_000);
});
