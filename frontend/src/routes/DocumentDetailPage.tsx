import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DocumentDetail } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Button } from "@/components/ui/Button";
import { MarkdownEditor } from "@/components/docs/MarkdownEditor";
import { useRenderedMarkdown } from "@/lib/useRenderedMarkdown";

export function DocumentDetailPage() {
    const { slug } = useParams<{ slug: string }>();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [isEditing, setIsEditing] = useState(false);
    const [draft, setDraft] = useState("");

    const { data, isPending, isError, error } = useQuery({
        queryKey: ["documents", slug],
        queryFn: () => api.get<DocumentDetail>(`/api/documents/${slug}`),
        enabled: !!slug,
    });

    const updateMutation = useMutation({
        mutationFn: (content_md: string) =>
            api.patch<DocumentDetail>(`/api/documents/${slug}`, { content_md }),
        onSuccess: (updated) => {
            queryClient.setQueryData(["documents", slug], updated);
            queryClient.invalidateQueries({ queryKey: ["documents"] });
            setIsEditing(false);
        },
    });

    const deleteMutation = useMutation({
        mutationFn: () => api.delete(`/api/documents/${slug}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["documents"] });
            navigate("/docs");
        },
    });

    const handleDelete = () => {
        if (data && window.confirm(`Удалить документ «${data.title}»? Действие нельзя отменить.`)) {
            deleteMutation.mutate();
        }
    };

    const previewHtml = useRenderedMarkdown(data?.content_md ?? "");

    if (isPending) return <Spinner />;
    if (isError) return <ErrorMessage message={(error as Error).message} />;
    if (!data) return null;

    return (
        <div className="mx-auto max-w-6xl">
            <div className="mb-6 flex items-center justify-between gap-4">
                <FocusHeading className="text-2xl font-bold">{data.title}</FocusHeading>
                <div className="flex gap-2">
                    <Link to="/docs" className="text-sm text-muted hover:text-foreground">
                        ← К списку
                    </Link>
                    {!isEditing && (
                        <>
                            <Button
                                variant="secondary"
                                onClick={() => {
                                    setDraft(data.content_md);
                                    setIsEditing(true);
                                }}
                            >
                                Редактировать
                            </Button>
                            <Button
                                variant="neutral"
                                disabled={deleteMutation.isPending}
                                onClick={handleDelete}
                            >
                                Удалить
                            </Button>
                        </>
                    )}
                </div>
            </div>

            {updateMutation.isError && (
                <div className="mb-4">
                    <ErrorMessage message={(updateMutation.error as Error).message} />
                </div>
            )}
            {deleteMutation.isError && (
                <div className="mb-4">
                    <ErrorMessage message={(deleteMutation.error as Error).message} />
                </div>
            )}

            {isEditing ? (
                <div>
                    <MarkdownEditor value={draft} onChange={setDraft} />
                    <div className="mt-4 flex gap-2">
                        <Button
                            variant="primary"
                            disabled={updateMutation.isPending}
                            onClick={() => updateMutation.mutate(draft)}
                        >
                            {updateMutation.isPending ? "Сохранение..." : "Сохранить"}
                        </Button>
                        <Button variant="neutral" onClick={() => setIsEditing(false)}>
                            Отмена
                        </Button>
                    </div>
                </div>
            ) : (
                <div className="markdown-body" dangerouslySetInnerHTML={{ __html: previewHtml }} />
            )}
        </div>
    );
}
