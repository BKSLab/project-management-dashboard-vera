import { Link } from "react-router-dom";
import type { DocumentListItem } from "@/lib/types";

interface DocumentListProps {
    documents: DocumentListItem[];
}

export function DocumentList({ documents }: DocumentListProps) {
    return (
        <ul className="divide-y divide-white/8 rounded-lg border border-white/20 bg-surface">
            {documents.map((document) => (
                <li key={document.id}>
                    <Link
                        to={`/docs/${document.slug}`}
                        className="flex items-center justify-between gap-4 px-6 py-4 transition-colors hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    >
                        <span className="font-semibold text-foreground">{document.title}</span>
                        <span className="text-xs text-muted">
                            {new Date(document.updated_at).toLocaleDateString("ru-RU")}
                        </span>
                    </Link>
                </li>
            ))}
        </ul>
    );
}
