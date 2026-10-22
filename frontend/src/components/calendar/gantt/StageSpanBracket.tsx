/**
 * Сводная полоса развёрнутой стадии — тонкая «скобка» от первой до последней даты её задач.
 * У свёрнутой стадии вместо неё рисуется полная сводная полоса (TimelineGrid).
 * `tone` — уже пропущенный через dataColor() цвет стадии.
 */
export function StageSpanBracket({ left, width, tone, title }: { left: number; width: number; tone: string; title: string }) {
    if (width <= 0) return null;
    return (
        <div
            className="absolute bottom-1.5 h-2 rounded-t-[2px] border-x-2 border-t-2"
            style={{ left, width, borderColor: tone, background: `color-mix(in oklch, ${tone} 14%, transparent)` }}
            title={title}
            data-stage-bracket=""
        />
    );
}
