import type { ReactNode } from "react";

const HIGHLIGHT_START = "__FTS_START__";
const HIGHLIGHT_END = "__FTS_END__";

interface SearchHighlightProps {
    text: string;
}

/** Преобразует серверные текстовые маркеры в React-разметку без вставки HTML. */
export function SearchHighlight({ text }: SearchHighlightProps) {
    const parts: ReactNode[] = [];
    let cursor = 0;
    let partIndex = 0;

    while (cursor < text.length) {
        const start = text.indexOf(HIGHLIGHT_START, cursor);
        if (start < 0) {
            parts.push(<span key={partIndex}>{text.slice(cursor)}</span>);
            break;
        }

        const matchStart = start + HIGHLIGHT_START.length;
        const end = text.indexOf(HIGHLIGHT_END, matchStart);
        if (end < 0) {
            parts.push(<span key={partIndex}>{text.slice(cursor)}</span>);
            break;
        }

        if (start > cursor) {
            parts.push(<span key={partIndex++}>{text.slice(cursor, start)}</span>);
        }
        parts.push(
            <mark
                key={partIndex++}
                className="rounded-sm bg-accent/25 px-0.5 font-semibold text-primary"
            >
                {text.slice(matchStart, end)}
            </mark>,
        );
        cursor = end + HIGHLIGHT_END.length;
    }

    return <>{parts}</>;
}
