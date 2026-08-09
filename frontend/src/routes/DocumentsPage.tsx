import { useDeferredValue, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DocumentListItem } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { DocumentList } from "@/components/docs/DocumentList";

function DocumentsSkeleton() {
    return (
        <ul
            role="status"
            aria-live="polite"
            aria-label="Загрузка документов..."
            className="divide-y divide-white/8 rounded-lg border border-white/20 bg-surface"
        >
            {Array.from({ length: 6 }).map((_, index) => (
                <li key={index} className="flex items-center justify-between gap-4 px-6 py-4">
                    <div className="min-w-0 flex-1 space-y-2">
                        <Skeleton className="h-4 w-2/5" />
                        <Skeleton className="h-3 w-4/5" />
                    </div>
                    <Skeleton className="h-3 w-14 shrink-0" />
                </li>
            ))}
        </ul>
    );
}

export function DocumentsPage() {
    const navigate = useNavigate();
    const [search, setSearch] = useState("");
    const deferredSearch = useDeferredValue(search.trim());

    const { data, isPending, isError, error } = useQuery({
        queryKey: deferredSearch ? ["documents", "search", deferredSearch] : ["documents"],
        queryFn: () =>
            api.get<DocumentListItem[]>(
                deferredSearch
                    ? `/api/v1/documents?search=${encodeURIComponent(deferredSearch)}`
                    : "/api/v1/documents"
            ),
    });

    return (
        <div className="mx-auto max-w-6xl">
            <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <FocusHeading className="text-2xl font-bold">Документы</FocusHeading>
                <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
                    <input
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        placeholder="Поиск по документам..."
                        aria-label="Поиск документов"
                        className="w-full rounded border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:w-72"
                    />
                    <Button variant="secondary" onClick={() => navigate("/docs/new")}>
                        + Новый документ
                    </Button>
                </div>
            </div>

            {isPending && <DocumentsSkeleton />}
            {isError && <ErrorMessage message={(error as Error).message} />}
            {data && data.length === 0 && (
                <EmptyState
                    message={deferredSearch ? "По вашему запросу ничего не найдено." : "Документов пока нет."}
                />
            )}
            {data && data.length > 0 && <DocumentList documents={data} />}
        </div>
    );
}
