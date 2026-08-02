import { Link } from "react-router-dom";
import type { DocumentListItem } from "@/lib/types";
import { SearchHighlight } from "@/components/ui/SearchHighlight";

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
                        <span className="min-w-0">
                            <span className="block font-semibold text-foreground">
                                <SearchHighlight text={document.search_title ?? document.title} />
                            </span>
                            {document.search_excerpt && (
                                <span className="mt-1 line-clamp-2 block text-sm text-muted">
                                    <span className="mr-1 font-semibold text-accent-secondary">
                                        {document.search_match_source === "slug" ? "Slug" : "В содержимом"}:
                                    </span>
                                    <SearchHighlight text={document.search_excerpt} />
                                </span>
                            )}
                        </span>
                        <span className="shrink-0 text-xs text-muted">
                            {new Date(document.updated_at).toLocaleDateString("ru-RU")}
                        </span>
                    </Link>
                </li>
            ))}
        </ul>
    );
}
