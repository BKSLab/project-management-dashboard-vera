import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGuard } from "@/components/layout/AuthGuard";
import { ProjectLayout } from "@/components/projects/ProjectLayout";
import { DashboardPage } from "@/routes/DashboardPage";
import { ProjectsPage } from "@/routes/ProjectsPage";
import { NewProjectPage } from "@/routes/NewProjectPage";
import { ProjectOverviewPage } from "@/routes/ProjectOverviewPage";
import { ProjectTeamPage } from "@/routes/ProjectTeamPage";
import { BoardPage } from "@/routes/BoardPage";
import { TasksListPage } from "@/routes/TasksListPage";
import { ProjectDocumentsPage } from "@/routes/ProjectDocumentsPage";
import { DocumentDetailPage } from "@/routes/DocumentDetailPage";
import { ProjectSettingsPage } from "@/routes/ProjectSettingsPage";
import { ProjectKnowledgePage } from "@/routes/ProjectKnowledgePage";
import { McpPage } from "@/routes/McpPage";
import { ProfilePage } from "@/routes/ProfilePage";
import { LoginPage } from "@/routes/LoginPage";
import { RegisterPage } from "@/routes/RegisterPage";
import { NotFoundPage } from "@/routes/NotFoundPage";
import { Skeleton } from "@/components/ui/States";

/**
 * Конструктор ИСР тянет React Flow и elkjs — самые тяжёлые зависимости
 * приложения. Отдельный чанк не даёт им попасть в стартовый бандл.
 */
const StructurePage = lazy(() =>
    import("@/routes/StructurePage").then((module) => ({ default: module.StructurePage })),
);
const ProjectCalendarPage = lazy(() =>
    import("@/routes/ProjectCalendarPage").then((module) => ({
        default: module.ProjectCalendarPage,
    })),
);

function StructureFallback() {
    return (
        <div role="status" aria-label="Загрузка структуры" className="flex h-full gap-3 p-4">
            <Skeleton className="h-full w-72 shrink-0" />
            <Skeleton className="h-full flex-1" />
        </div>
    );
}

function CalendarFallback() {
    return (
        <div role="status" aria-label="Загрузка календаря" className="flex h-full gap-3 p-4">
            <Skeleton className="h-full w-72 shrink-0" />
            <Skeleton className="h-full flex-1" />
        </div>
    );
}

/** Приложение за стеной входа: всё внутри требует действительной сессии. */
function ProtectedApp() {
    return (
        <AuthGuard>
            <AppShell>
                <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/projects" element={<ProjectsPage />} />
                    <Route path="/projects/new" element={<NewProjectPage />} />
                    <Route path="/profile" element={<ProfilePage />} />
                    <Route path="/mcp" element={<McpPage />} />
                    <Route path="/projects/:projectKey" element={<ProjectLayout />}>
                        <Route index element={<ProjectOverviewPage />} />
                        <Route path="team" element={<ProjectTeamPage />} />
                        <Route path="board" element={<BoardPage />} />
                        <Route path="tasks" element={<TasksListPage />} />
                        <Route
                            path="calendar"
                            element={
                                <Suspense fallback={<CalendarFallback />}>
                                    <ProjectCalendarPage />
                                </Suspense>
                            }
                        />
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
                        <Route path="knowledge" element={<ProjectKnowledgePage />} />
                        <Route path="settings" element={<ProjectSettingsPage />} />
                    </Route>
                    <Route path="*" element={<NotFoundPage />} />
                </Routes>
            </AppShell>
        </AuthGuard>
    );
}

function App() {
    return (
        <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="*" element={<ProtectedApp />} />
        </Routes>
    );
}

export default App;
