import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ProjectLayout } from "@/components/projects/ProjectLayout";
import { DashboardPage } from "@/routes/DashboardPage";
import { ProjectsPage } from "@/routes/ProjectsPage";
import { NewProjectPage } from "@/routes/NewProjectPage";
import { ProjectOverviewPage } from "@/routes/ProjectOverviewPage";
import { BoardPage } from "@/routes/BoardPage";
import { TasksListPage } from "@/routes/TasksListPage";
import { StructurePage } from "@/routes/StructurePage";
import { ProjectDocumentsPage } from "@/routes/ProjectDocumentsPage";
import { DocumentDetailPage } from "@/routes/DocumentDetailPage";
import { ProjectSettingsPage } from "@/routes/ProjectSettingsPage";
import { NotFoundPage } from "@/routes/NotFoundPage";

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
                    <Route path="structure" element={<StructurePage />} />
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
