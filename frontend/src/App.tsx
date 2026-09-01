import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ProjectLayout } from "@/components/projects/ProjectLayout";
import { DashboardPage } from "@/routes/DashboardPage";
import { ProjectsPage } from "@/routes/ProjectsPage";
import { NewProjectPage } from "@/routes/NewProjectPage";
import { ProjectOverviewPage } from "@/routes/ProjectOverviewPage";
import { BoardPage } from "@/routes/BoardPage";
import { TasksListPage } from "@/routes/TasksListPage";
import { ProjectDocumentsPage } from "@/routes/ProjectDocumentsPage";
import { DocumentDetailPage } from "@/routes/DocumentDetailPage";
import { ProjectSettingsPage } from "@/routes/ProjectSettingsPage";
import { NotFoundPage } from "@/routes/NotFoundPage";
import { Skeleton } from "@/components/ui/States";

/**
 * Конструктор ИСР тянет React Flow и elkjs — самые тяжёлые зависимости
 * приложения. Отдельный чанк не даёт им попасть в стартовый бандл.
 */
const StructurePage = lazy(() =>
    import("@/routes/StructurePage").then((module) => ({ default: module.StructurePage })),
);

function StructureFallback() {
    return (
        <div role="status" aria-label="Загрузка структуры" className="flex h-full gap-3 p-4">
            <Skeleton className="h-full w-72 shrink-0" />
            <Skeleton className="h-full flex-1" />
        </div>
    );
}

function App() {
    return (
        <AppShell>
            <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/projects/new" element={<NewProjectPage />} />
                <Route path="/projects/:projectKey" element={<ProjectLayout />}>
                    <Route index element={<ProjectOverviewPage />} />
                    <Route path="board" element={<BoardPage />} />
                    <Route path="tasks" element={<TasksListPage />} />
                    <Route
                        path="structure"
                        element={
                            <Suspense fallback={<StructureFallback />}>
                                <StructurePage />
                            </Suspense>
                        }
                    />
                    <Route path="docs" element={<ProjectDocumentsPage />} />
                    <Route path="docs/:slug" element={<DocumentDetailPage />} />
                    <Route path="settings" element={<ProjectSettingsPage />} />
                </Route>
                <Route path="*" element={<NotFoundPage />} />
            </Routes>
        </AppShell>
    );
}

export default App;
