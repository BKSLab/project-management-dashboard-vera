import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DocumentListItem } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { DocumentList } from "@/components/docs/DocumentList";

export function DocumentsPage() {
    const navigate = useNavigate();

    const { data, isPending, isError, error } = useQuery({
        queryKey: ["documents"],
        queryFn: () => api.get<DocumentListItem[]>("/api/documents"),
    });

    return (
        <div className="mx-auto max-w-6xl">
            <div className="mb-6 flex items-center justify-between gap-4">
                <FocusHeading className="text-2xl font-bold">Документы</FocusHeading>
                <Button variant="secondary" onClick={() => navigate("/docs/new")}>
                    + Новый документ
                </Button>
            </div>

            {isPending && <Spinner />}
            {isError && <ErrorMessage message={(error as Error).message} />}
            {data && data.length === 0 && <EmptyState message="Документов пока нет." />}
            {data && data.length > 0 && <DocumentList documents={data} />}
        </div>
    );
}
