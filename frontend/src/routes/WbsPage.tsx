import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { WbsItem, WbsNode as WbsNodeType, WbsRole } from "@/lib/types";
import { FocusHeading } from "@/components/ui/FocusHeading";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { ItemForm, WbsNode } from "@/components/wbs/WbsNode";
import { useUiStore } from "@/stores/ui";

export function WbsPage() {
    const queryClient = useQueryClient();
    const [isAddingPhase, setIsAddingPhase] = useState(false);

    const { data, isPending, isError, error } = useQuery({
        queryKey: ["wbs", "tree"],
        queryFn: () => api.get<WbsNodeType[]>("/api/wbs/tree"),
    });

    const toggleWbsNode = useUiStore((state) => state.toggleWbsNode);
    const expandedOnce = useRef(false);

    useEffect(() => {
        if (data && !expandedOnce.current) {
            expandedOnce.current = true;
            data.forEach((root) => toggleWbsNode(root.id));
        }
    }, [data, toggleWbsNode]);

    const createPhaseMutation = useMutation({
        mutationFn: (vars: { title: string; role: WbsRole | null }) =>
            api.post<WbsItem>("/api/wbs/items", {
                parent_id: null,
                title: vars.title,
                role: vars.role,
                phase_name: vars.title,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["wbs", "tree"] });
            queryClient.invalidateQueries({ queryKey: ["kanban", "tasks"] });
            setIsAddingPhase(false);
        },
    });

    return (
        <div className="mx-auto max-w-6xl">
            <div className="mb-6 flex items-center justify-between gap-4">
                <FocusHeading className="text-2xl font-bold">ИСР</FocusHeading>
                {!isAddingPhase && (
                    <Button variant="secondary" onClick={() => setIsAddingPhase(true)}>
                        + Новая фаза
                    </Button>
                )}
            </div>

            {isAddingPhase && (
                <div className="mb-4">
                    <ItemForm
                        initialTitle=""
                        initialRole={null}
                        submitLabel="Добавить фазу"
                        isPending={createPhaseMutation.isPending}
                        onSubmit={(title, role) => createPhaseMutation.mutate({ title, role })}
                        onCancel={() => setIsAddingPhase(false)}
                    />
                </div>
            )}

            {isPending && <Spinner />}
            {isError && <ErrorMessage message={(error as Error).message} />}
            {data && data.length === 0 && <EmptyState message="Дерево ИСР пусто." />}
            {data && data.length > 0 && (
                <ul className="rounded-lg border border-white/20 bg-surface p-2">
                    {data.map((node) => (
                        <WbsNode key={node.id} node={node} depth={0} />
                    ))}
                </ul>
            )}
        </div>
    );
}
