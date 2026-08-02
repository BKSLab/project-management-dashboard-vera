import { Routes, Route } from "react-router-dom";
import { SkipLink } from "@/components/ui/SkipLink";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { HomePage } from "@/routes/HomePage";
import { DocumentsPage } from "@/routes/DocumentsPage";
import { NewDocumentPage } from "@/routes/NewDocumentPage";
import { DocumentDetailPage } from "@/routes/DocumentDetailPage";
import { WbsPage } from "@/routes/WbsPage";
import { KanbanPage } from "@/routes/KanbanPage";

function App() {
    return (
        <div className="flex min-h-screen min-w-0 flex-col overflow-x-hidden">
            <SkipLink />
            <Header />
            <main id="main-content" className="min-w-0 w-full flex-1 px-4 py-8">
                <Routes>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/docs" element={<DocumentsPage />} />
                    <Route path="/docs/new" element={<NewDocumentPage />} />
                    <Route path="/docs/:slug" element={<DocumentDetailPage />} />
                    <Route path="/wbs" element={<WbsPage />} />
                    <Route path="/kanban" element={<KanbanPage />} />
                </Routes>
            </main>
            <Footer />
        </div>
    );
}

export default App;
