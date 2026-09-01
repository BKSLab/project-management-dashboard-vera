import { Compass } from "lucide-react";
import { Page } from "@/components/layout/AppShell";
import { LinkButton } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/States";

export function NotFoundPage() {
    return (
        <Page className="max-w-2xl">
            <EmptyState
                title="Страница не найдена"
                description="Проверьте адрес или вернитесь к списку проектов."
                icon={<Compass size={24} />}
                action={<LinkButton to="/">На дашборд</LinkButton>}
            />
        </Page>
    );
}
