import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Page } from "@/components/layout/AppShell";
import { Button, LinkButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorMessage } from "@/components/ui/States";
import { ProjectForm } from "@/components/projects/ProjectForm";
import {
    EMPTY_PROJECT_FORM,
    isProjectFormValid,
    toProjectPayload,
    type ProjectFormValues,
} from "@/lib/projectForm";

export function NewProjectPage() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [values, setValues] = useState<ProjectFormValues>(EMPTY_PROJECT_FORM);

    const createMutation = useMutation({
        mutationFn: () => api.post<Project>(endpoints.projects(), toProjectPayload(values)),
        onSuccess: (project) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.projects });
            queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
            navigate(`/projects/${project.key}`);
        },
    });

    return (
        <Page className="max-w-3xl">
            <header className="flex flex-col gap-0.5">
                <h1 className="text-lg font-semibold text-primary">Новый проект</h1>
                <p className="text-[13px] text-muted">
                    Доска канбана со стандартными стадиями создаётся автоматически.
                </p>
            </header>

            <Card className="flex flex-col gap-4 p-5">
                {createMutation.error && (
                    <ErrorMessage
                        title="Не удалось создать проект"
                        message={(createMutation.error as Error).message}
                    />
                )}

                <ProjectForm values={values} onChange={setValues} />

                <div className="flex justify-end gap-2 border-t border-line-subtle pt-4">
                    <LinkButton to="/projects">Отмена</LinkButton>
                    <Button
                        variant="primary"
                        disabled={!isProjectFormValid(values) || createMutation.isPending}
                        onClick={() => createMutation.mutate()}
                    >
                        Создать проект
                    </Button>
                </div>
            </Card>
        </Page>
    );
}
