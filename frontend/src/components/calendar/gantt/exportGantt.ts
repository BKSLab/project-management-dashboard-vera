import { pdfPageSize } from "@/lib/ganttView";

/**
 * Снимок листа Ганта (GanttSheet) в PNG или PDF — целиком, а не видимый кусок: лист рисуется
 * вне экрана в натуральную ширину. Библиотеки грузятся только при первой выгрузке, чтобы не
 * тяжелить основной бандл (html-to-image ~ 20 КБ, jspdf ~ 350 КБ).
 */
async function renderPng(node: HTMLElement): Promise<{ dataUrl: string; width: number; height: number }> {
    const { toPng } = await import("html-to-image");
    const width = node.scrollWidth;
    const height = node.scrollHeight;
    const background = getComputedStyle(document.body).backgroundColor || "#ffffff";
    // Очень длинная шкала (годы по неделям) — снижаем плотность, чтобы canvas не упёрся в лимит браузера.
    const pixelRatio = Math.max(1, Math.min(2, 16_000 / Math.max(width, height)));
    const dataUrl = await toPng(node, {
        width,
        height,
        pixelRatio,
        backgroundColor: background,
        cacheBust: true,
        style: { transform: "none", position: "static", left: "0", top: "0" },
    });
    return { dataUrl, width, height };
}

function download(href: string, fileName: string) {
    const link = document.createElement("a");
    link.href = href;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
}

export async function exportGanttPng(node: HTMLElement, fileName: string) {
    const { dataUrl } = await renderPng(node);
    download(dataUrl, fileName);
}

export async function exportGanttPdf(node: HTMLElement, fileName: string) {
    const [{ dataUrl, width, height }, { jsPDF }] = await Promise.all([renderPng(node), import("jspdf")]);
    const page = pdfPageSize(width, height);
    const pdf = new jsPDF({ orientation: page.orientation, unit: "mm", format: [page.width, page.height], compress: true });
    pdf.addImage(dataUrl, "PNG", 0, 0, page.width, page.height, undefined, "FAST");
    const blob = pdf.output("blob");
    const url = URL.createObjectURL(blob);
    download(url, fileName);
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
