import { useEffect, useState } from "react";
import { renderMarkdown } from "@/lib/markdown";

export function useRenderedMarkdown(markdown: string): string {
    const [html, setHtml] = useState("");

    useEffect(() => {
        let cancelled = false;
        renderMarkdown(markdown).then((rendered) => {
            if (!cancelled) setHtml(rendered);
        });
        return () => {
            cancelled = true;
        };
    }, [markdown]);

    return html;
}
