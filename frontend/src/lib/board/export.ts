import { boundsOfPoints, inflateBox, polylineMidpoint, polylinePath, shapePath, unionBoxes, type Box } from "@/lib/board/geometry";
import { arrowHeadPolygon } from "@/lib/board/routing";
import { connectorPoints, nodeLookup, sortedObjects, type Scene, type SceneObject, type ShapeObject, type StickerObject } from "@/lib/board/scene";
import { normalizeStickerColor, stickerSurface } from "@/lib/board/stickers";
import { FONT_SIZE_PX, isConnectorKind, type PaletteColor, type Point } from "@/lib/board/types";

type VisibleColor = Exclude<PaletteColor, "none">;
const COLORS: VisibleColor[] = ["neutral", "yellow", "blue", "green", "red", "violet"];

/** Только автономные цвета, не CSS vars, url(), currentColor или произвольный CSS. */
export interface ExportPalette {
    stroke: Record<VisibleColor, string>;
    fill: Record<VisibleColor, string>;
    text: string;
    background: string;
    labelBackground: string;
    stickerInk: string;
    stickerBorder: string;
    stickerFill?: (hex: string) => string;
}

export const LIGHT_EXPORT_PALETTE: ExportPalette = {
    stroke: { neutral: "#18181b", yellow: "#b45309", blue: "#1d4ed8", green: "#15803d", red: "#b91c1c", violet: "#8b5cf6" },
    fill: { neutral: "#f3efe4", yellow: "#fff19a", blue: "#c9edff", green: "#d8f5b5", red: "#ffbbb5", violet: "#e4d2ff" },
    text: "#18181b", background: "#ffffff", labelBackground: "#f5f5f7", stickerInk: "#27241d", stickerBorder: "#c9c2a7",
};

export interface StickerExportText {
    title?: string;
    body?: string;
    status?: string;
}

export interface SVGExportOptions {
    /** undefined — вся доска; пустое выделение — ошибка, а не вся доска. */
    selectedKeys?: Iterable<string>;
    padding?: number;
    palette?: ExportPalette;
    /** По умолчанию фон текущей palette; "transparent" — прозрачный. */
    background?: string;
    /** Дополнительный текст карточек из внешнего справочника, без сетевых обращений. */
    stickerText?: (object: StickerObject) => StickerExportText;
}

export interface SVGExport {
    svg: string;
    blob: Blob;
    bounds: Box;
    width: number;
    height: number;
    objectCount: number;
}

export interface PNGExportOptions extends SVGExportOptions {
    scale?: number;
    /** Лимиты можно уменьшать, но нельзя увеличивать выше PNG_LIMITS. */
    maxDimension?: number;
    maxPixels?: number;
    /** Уменьшить изображение до лимитов (по умолчанию) либо отказаться. */
    overflow?: "shrink" | "error";
    timeoutMs?: number;
    signal?: AbortSignal;
}

export interface PNGExport {
    blob: Blob;
    width: number;
    height: number;
    /** Реальный масштаб относительно координат доски после ограничения размеров. */
    scale: number;
    bounds: Box;
    objectCount: number;
}

export const PNG_LIMITS = Object.freeze({ maxDimension: 8192, maxPixels: 16_777_216, timeoutMs: 30_000 });

/** XML 1.0: запрещённые codepoints заменяем, все значимые символы экранируем. */
export function escapeXML(value: string): string {
    return Array.from(value, (character) => {
        const point = character.codePointAt(0)!;
        if (!(point === 9 || point === 10 || point === 13 || (point >= 32 && point <= 0xd7ff)
            || (point >= 0xe000 && point <= 0xfffd) || (point >= 0x10000 && point <= 0x10ffff))) return "�";
        return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" } as Record<string, string>)[character] ?? character;
    }).join("");
}

/** Узкий whitelist paint: hex, transparent/none и числовой rgb(a). */
function safeColor(value: string): string {
    if (typeof value !== "string") throw new Error("Недопустимый цвет экспорта.");
    const color = value.trim();
    if (/^#(?:[\da-f]{3}|[\da-f]{4}|[\da-f]{6}|[\da-f]{8})$/i.test(color) || /^(?:transparent|none)$/.test(color)) return color;
    const match = /^rgba?\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*,\s*(0(?:\.\d+)?|1(?:\.0+)?))?\s*\)$/.exec(color);
    if (match && match.slice(1, 4).every((channel) => Number(channel) <= 255)
        && (color.startsWith("rgba(") === (match[4] !== undefined))) return color;
    throw new Error("Недопустимый цвет экспорта. Передайте цвет в HEX или RGB.");
}

/**
 * Снять реальные цвета текущей темы. Единственный DOM-helper: не читает объекты/viewport.
 * Временный color-probe разрешает вложенные CSS vars; 1×1 canvas переводит современные
 * CSS цвета (включая бумажный OKLCH стикеров) в автономный RGBA.
 */
export function resolveExportPalette(root: Element): ExportPalette {
    const doc = root.ownerDocument;
    const view = doc.defaultView;
    if (!view) throw new Error("Не удалось определить тему доски.");
    const sample = (expression: string): string => {
        const probe = doc.createElement("span");
        probe.style.cssText = "position:absolute;visibility:hidden;pointer-events:none";
        probe.style.color = expression;
        root.appendChild(probe);
        try {
            const computed = view.getComputedStyle(probe).color;
            try { return safeColor(computed); } catch { /* OKLCH/color() → sRGB below */ }
            const canvas = doc.createElement("canvas");
            canvas.width = canvas.height = 1;
            const context = canvas.getContext("2d", { willReadFrequently: true });
            if (!context) throw new Error("Браузер не поддерживает экспорт изображения.");
            context.fillStyle = computed;
            context.fillRect(0, 0, 1, 1);
            const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data;
            return `rgba(${r}, ${g}, ${b}, ${a / 255})`;
        } finally {
            probe.remove();
        }
    };
    return {
        stroke: Object.fromEntries(COLORS.map((color) => [color, sample(`var(--board-stroke-${color})`)])) as ExportPalette["stroke"],
        fill: Object.fromEntries(COLORS.map((color) => [color, sample(`var(--board-fill-${color})`)])) as ExportPalette["fill"],
        text: sample("var(--color-text-primary)"),
        background: sample("var(--color-bg-surface)"),
        labelBackground: sample("var(--color-bg-surface-2)"),
        stickerInk: sample("var(--surface-note-ink)"),
        stickerBorder: sample("var(--surface-note-border)"),
        stickerFill: (hex) => sample(stickerSurface(hex)),
    };
}

function validateNumber(value: number, name: string, min: number, max: number): number {
    if (!Number.isFinite(value) || value < min || value > max) throw new Error(`Недопустимое значение: ${name}.`);
    return value;
}

function validateObject(object: SceneObject): void {
    for (const [name, value] of Object.entries({ x: object.x, y: object.y, w: object.w, h: object.h, z: object.z })) {
        validateNumber(value, name, name === "w" || name === "h" ? 0 : -10_000_000, 10_000_000);
    }
    if (object.type === "shape") {
        if (!["rect", "ellipse", "diamond", "text", "line", "arrow"].includes(object.kind)) throw new Error("Неизвестная фигура доски.");
        if (!COLORS.includes(object.style.stroke as VisibleColor) && object.style.stroke !== "none") throw new Error("Неизвестный цвет обводки.");
        if (!COLORS.includes(object.style.fill as VisibleColor) && object.style.fill !== "none") throw new Error("Неизвестный цвет заливки.");
        if (![1, 2, 4].includes(object.style.stroke_width) || !Object.hasOwn(FONT_SIZE_PX, object.style.font_size)) throw new Error("Недопустимый стиль фигуры.");
        for (const point of object.points ?? []) {
            validateNumber(point[0], "координата линии", -10_000_000, 10_000_000);
            validateNumber(point[1], "координата линии", -10_000_000, 10_000_000);
        }
    }
}

interface TextLayout { lines: string[]; width: number; height: number; }

/** Детерминированный перенос без DOM/шрифтов. SVG textLength гарантирует ширину строки. */
function wrapText(text: string, width: number, fontSize: number, maxHeight = Infinity): TextLayout {
    const capacity = Math.max(1, Math.floor(width / (fontSize * 0.62)));
    const lineHeight = fontSize * 1.35;
    const maxLines = Math.max(0, Math.floor(maxHeight / lineHeight));
    const lines: string[] = [];
    let truncated = false;
    outer: for (const paragraph of text.replace(/\r\n?/g, "\n").split("\n")) {
        const characters = Array.from(paragraph);
        if (characters.length === 0) {
            if (lines.length >= maxLines) { truncated = true; break; }
            lines.push("");
        }
        while (characters.length > 0) {
            if (lines.length >= maxLines) { truncated = true; break outer; }
            let take = Math.min(capacity, characters.length);
            if (take < characters.length) {
                const whitespace = characters.slice(0, take).lastIndexOf(" ");
                if (whitespace > capacity / 2) take = whitespace + 1;
            }
            lines.push(characters.splice(0, take).join("").trimEnd());
        }
    }
    if (truncated && lines.length) {
        lines[lines.length - 1] = Array.from(lines[lines.length - 1]).slice(0, Math.max(0, capacity - 1)).join("") + "…";
    }
    return { lines, width: Math.min(width, Math.max(0, ...lines.map((line) => Array.from(line).length * fontSize * 0.62))), height: lines.length * lineHeight };
}

function renderText(text: string, box: Box, fontSize: number, color: string, id: string, align: "left" | "center" = "left", bold = false, verticalCenter = false, prepared?: TextLayout): string {
    if (!text || box.w <= 0 || box.h <= 0) return "";
    const layout = prepared ?? wrapText(text, box.w, fontSize, box.h);
    const x = align === "left" ? box.x : box.x + box.w / 2;
    const top = box.y + (verticalCenter ? Math.max(0, (box.h - layout.height) / 2) : 0);
    const lines = layout.lines.map((line, index) => {
        const length = Math.min(box.w, Array.from(line).length * fontSize * 0.62);
        const constrained = length > 0 ? ` textLength="${length}" lengthAdjust="spacingAndGlyphs"` : "";
        return `<tspan x="${x}" y="${top + fontSize + index * fontSize * 1.35}"${constrained}>${escapeXML(line)}</tspan>`;
    }).join("");
    return `<defs><clipPath id="${id}"><rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}"/></clipPath></defs><text clip-path="url(#${id})" fill="${escapeXML(safeColor(color))}" font-family="Arial, sans-serif" font-size="${fontSize}" font-weight="${bold ? 600 : 400}" text-anchor="${align === "left" ? "start" : "middle"}" xml:space="preserve">${lines}</text>`;
}

interface RenderedObject { svg: string; bounds: Box; }

function renderSticker(object: StickerObject, palette: ExportPalette, options: SVGExportOptions, index: number): RenderedObject {
    const { x, y, w, h } = object;
    const hex = normalizeStickerColor(object.sticker.color);
    const fill = safeColor(palette.stickerFill?.(hex) ?? hex);
    // Старый контракт содержит только body. Новые необязательные title/status не теряем.
    const extra = object.sticker as typeof object.sticker & StickerExportText;
    const text = { title: extra.title, body: object.sticker.body, status: extra.status, ...options.stickerText?.(object) };
    const inset = Math.min(12, w / 4, h / 4);
    const inner: Box = { x: x + inset, y: y + inset, w: Math.max(0, w - 2 * inset), h: Math.max(0, h - 2 * inset) };
    const titleHeight = text.title ? Math.min(inner.h, 40) : 0;
    const statusHeight = text.status ? Math.min(Math.max(0, inner.h - titleHeight), 22) : 0;
    const bodyHeight = Math.max(0, inner.h - titleHeight - statusHeight);
    const svg = `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="4" fill="${escapeXML(fill)}" stroke="${escapeXML(safeColor(palette.stickerBorder))}" stroke-width="1"/>`
        + renderText(text.title ?? "", { ...inner, h: titleHeight }, 14, palette.stickerInk, `be-${index}-title`, "left", true)
        + renderText(text.body ?? "", { ...inner, y: inner.y + titleHeight, h: bodyHeight }, 14, palette.stickerInk, `be-${index}-body`)
        + renderText(text.status ?? "", { ...inner, y: inner.y + inner.h - statusHeight, h: statusHeight }, 12, palette.stickerInk, `be-${index}-status`);
    return { svg, bounds: inflateBox(object, 0.5) };
}

function renderShape(object: ShapeObject, scene: Scene, palette: ExportPalette, index: number): RenderedObject {
    const { style, x, y, w, h } = object;
    const strokeWidth = style.stroke_width;
    const stroke = safeColor(style.stroke === "none" ? (isConnectorKind(object.kind) ? palette.stroke.neutral : "none") : palette.stroke[style.stroke]);
    const fill = safeColor(style.fill === "none" ? "none" : palette.fill[style.fill]);
    const dash = style.dash === "dashed" ? ` stroke-dasharray="${strokeWidth * 4} ${strokeWidth * 3}"` : "";
    const fontSize = FONT_SIZE_PX[style.font_size];
    if (!isConnectorKind(object.kind)) {
        const horizontal = object.kind === "ellipse" ? w * 0.14 : object.kind === "diamond" ? w * 0.24 : Math.min(10, w / 2);
        const vertical = object.kind === "ellipse" ? h * 0.12 : object.kind === "diamond" ? h * 0.18 : Math.min(6, h / 2);
        const svg = `<path transform="translate(${x} ${y})" d="${escapeXML(shapePath(object.kind, w, h, strokeWidth / 2))}" fill="${escapeXML(fill)}" stroke="${escapeXML(stroke)}" stroke-width="${strokeWidth}" stroke-linejoin="round"${dash}/>`
            + renderText(object.label, { x: x + horizontal, y: y + vertical, w: w - horizontal * 2, h: h - vertical * 2 }, fontSize, palette.text, `be-${index}-label`, style.text_align, false, true);
        return { svg, bounds: inflateBox(object, strokeWidth / 2) };
    }
    const points = connectorPoints({
        ...object,
        points: object.points && object.points.length >= 2 ? object.points : [[x, y], [x + w, y + h]],
    }, nodeLookup(scene));
    const heads: Point[][] = [];
    if (style.start_head === "arrow") {
        const toward = points.slice(1).find((point) => point[0] !== points[0][0] || point[1] !== points[0][1]);
        if (toward) heads.push(arrowHeadPolygon(toward, points[0], strokeWidth));
    }
    if (style.end_head === "arrow") {
        const end = points[points.length - 1];
        const toward = points.slice(0, -1).reverse().find((point) => point[0] !== end[0] || point[1] !== end[1]);
        if (toward) heads.push(arrowHeadPolygon(toward, end, strokeWidth));
    }
    let svg = `<path d="${escapeXML(polylinePath(points))}" fill="none" stroke="${escapeXML(stroke)}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round"${dash}/>`
        + heads.map((head) => `<path d="${escapeXML(polylinePath(head))} Z" fill="${escapeXML(stroke)}" stroke="${escapeXML(stroke)}" stroke-width="1" stroke-linejoin="round"/>`).join("");
    const boxes = [inflateBox(boundsOfPoints(points), strokeWidth / 2), ...heads.map((head) => inflateBox(boundsOfPoints(head), 0.5))];
    if (object.label) {
        const layout = wrapText(object.label, 228, fontSize, 4096);
        const mid = polylineMidpoint(points);
        const labelBox = { x: mid[0] - (layout.width + 12) / 2, y: mid[1] - (layout.height + 2) / 2, w: layout.width + 12, h: layout.height + 2 };
        boxes.push(labelBox);
        svg += `<rect x="${labelBox.x}" y="${labelBox.y}" width="${labelBox.w}" height="${labelBox.h}" rx="3" fill="${escapeXML(safeColor(palette.labelBackground))}"/>`
            + renderText(object.label, { x: labelBox.x + 6, y: labelBox.y + 1, w: labelBox.w - 12, h: labelBox.h - 2 }, fontSize, palette.text, `be-${index}-label`, "center", false, false, layout);
    }
    return { svg, bounds: unionBoxes(boxes)! };
}

/** Синхронный чистый экспорт всей Scene; порядок слоёв общий с редактором. */
export function exportSVG(scene: Scene, options: SVGExportOptions = {}): SVGExport {
    const padding = validateNumber(options.padding ?? 24, "отступ", 0, 100_000);
    const selected = options.selectedKeys === undefined ? null : new Set(options.selectedKeys);
    const objects = sortedObjects(scene).filter((object) => !selected || selected.has(object.key));
    if (!objects.length) throw new Error(selected ? "Выделите объекты для экспорта." : "На доске нет объектов для экспорта.");
    // Проверяем также невыделенные узлы: они задают текущие привязки стрелок.
    for (const object of scene.values()) validateObject(object);
    const palette = options.palette ?? LIGHT_EXPORT_PALETTE;
    const background = safeColor(options.background ?? palette.background);
    const rendered = objects.map((object, index) => ({
        ...object.type === "sticker" ? renderSticker(object, palette, options, index) : renderShape(object, scene, palette, index),
        key: object.key,
    }));
    const bounds = inflateBox(unionBoxes(rendered.map((object) => object.bounds))!, padding);
    // SVG тоже не должен содержать нулевой viewBox.
    bounds.w = Math.max(1, bounds.w);
    bounds.h = Math.max(1, bounds.h);
    const width = Math.ceil(bounds.w);
    const height = Math.ceil(bounds.h);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="${bounds.x} ${bounds.y} ${bounds.w} ${bounds.h}"><rect x="${bounds.x}" y="${bounds.y}" width="${bounds.w}" height="${bounds.h}" fill="${escapeXML(background)}"/>${rendered.map((object) => `<g data-key="${escapeXML(object.key)}">${object.svg}</g>`).join("")}</svg>`;
    return { svg, blob: new Blob([svg], { type: "image/svg+xml;charset=utf-8" }), bounds, width, height, objectCount: objects.length };
}

/** Рассчитать canvas до выделения памяти; округление никогда не превышает бюджет. */
export function pngDimensions(width: number, height: number, options: PNGExportOptions = {}): { width: number; height: number; scale: number } {
    validateNumber(width, "ширина", 1, 100_000_000);
    validateNumber(height, "высота", 1, 100_000_000);
    const scale = validateNumber(options.scale ?? 2, "масштаб", 0.01, 100);
    const dimension = Math.floor(validateNumber(options.maxDimension ?? PNG_LIMITS.maxDimension, "размер PNG", 1, PNG_LIMITS.maxDimension));
    const pixels = Math.floor(validateNumber(options.maxPixels ?? PNG_LIMITS.maxPixels, "число пикселей", 1, PNG_LIMITS.maxPixels));
    const desiredW = Math.ceil(width * scale);
    const desiredH = Math.ceil(height * scale);
    if (desiredW <= dimension && desiredH <= dimension && desiredW * desiredH <= pixels) return { width: desiredW, height: desiredH, scale };
    if (options.overflow === "error") throw new Error("Доска слишком большая для PNG. Уменьшите масштаб или экспортируйте выделение.");
    const fit = Math.min(scale, dimension / width, dimension / height, Math.sqrt(pixels / (width * height)));
    let w = Math.max(1, Math.floor(width * fit));
    let h = Math.max(1, Math.floor(height * fit));
    // Один пиксель по короткой стороне может превысить budget у очень вытянутой доски.
    if (w * h > pixels) {
        if (w >= h) w = Math.max(1, Math.floor(pixels / h));
        else h = Math.max(1, Math.floor(pixels / w));
    }
    return { width: w, height: h, scale: Math.min(w / width, h / height) };
}

/** PNG только из собственного SVG. URL/canvas очищаются и при отказе/отмене/таймауте. */
export async function exportPNG(scene: Scene, options: PNGExportOptions = {}): Promise<PNGExport> {
    const exported = exportSVG(scene, options);
    const dimensions = pngDimensions(exported.width, exported.height, options);
    const timeoutMs = validateNumber(options.timeoutMs ?? PNG_LIMITS.timeoutMs, "время экспорта", 1, PNG_LIMITS.timeoutMs);
    if (options.signal?.aborted) throw new Error("Экспорт отменён.");
    if (typeof document === "undefined" || typeof Image === "undefined" || typeof URL.createObjectURL !== "function") {
        throw new Error("PNG можно экспортировать только в браузере.");
    }
    const canvas = document.createElement("canvas");
    canvas.width = dimensions.width;
    canvas.height = dimensions.height;
    let url: string | undefined;
    let img: HTMLImageElement | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let abort: (() => void) | undefined;
    try {
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Браузер не смог создать изображение. Попробуйте экспорт в SVG.");
        // Ограничиваем также intrinsic SVG size до загрузки Image, иначе растеризатор
        // мог бы выделить огромную поверхность ещё до drawImage.
        const rasterSVG = exported.svg.replace(
            `width="${exported.width}" height="${exported.height}"`,
            `width="${dimensions.width}" height="${dimensions.height}"`,
        );
        url = URL.createObjectURL(new Blob([rasterSVG], { type: "image/svg+xml;charset=utf-8" }));
        img = new Image();
        const image = img;
        const blob = await new Promise<Blob>((resolve, reject) => {
            const fail = (message: string) => reject(new Error(message));
            abort = () => fail("Экспорт отменён.");
            options.signal?.addEventListener("abort", abort, { once: true });
            timer = setTimeout(() => fail("Экспорт занял слишком много времени. Попробуйте SVG или меньшее выделение."), timeoutMs);
            image.onerror = () => fail("Не удалось прочитать изображение доски.");
            image.onload = () => {
                try {
                    context.drawImage(image, 0, 0, dimensions.width, dimensions.height);
                    canvas.toBlob((result) => result ? resolve(result) : fail("Браузер не смог сохранить PNG."), "image/png");
                } catch {
                    fail("Не удалось создать PNG. Попробуйте экспорт в SVG.");
                }
            };
            image.src = url!;
        });
        return { blob, ...dimensions, bounds: exported.bounds, objectCount: exported.objectCount };
    } finally {
        if (timer !== undefined) clearTimeout(timer);
        if (abort) options.signal?.removeEventListener("abort", abort);
        if (img) { img.onload = null; img.onerror = null; img.src = ""; }
        if (url !== undefined) URL.revokeObjectURL(url);
        canvas.width = canvas.height = 0;
    }
}
