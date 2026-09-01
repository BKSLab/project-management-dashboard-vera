import { useEffect, type ReactNode } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { onUnauthorized } from "@/lib/api";
import { useCurrentUser } from "@/lib/useAuth";
import { Skeleton } from "@/components/ui/States";

/**
 * Закрывает приложение целиком: без действительной сессии не показывается
 * ничего, включая дашборд. Страницы входа и регистрации живут вне guard.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
    const location = useLocation();
    const navigate = useNavigate();
    const { data: user, isPending, error } = useCurrentUser();

    useEffect(() => {
        // Сессия могла протухнуть в уже открытой вкладке.
        return onUnauthorized(() => {
            navigate("/login", { replace: true, state: { from: location.pathname } });
        });
    }, [navigate, location.pathname]);

    if (isPending) {
        return (
            <div
                role="status"
                aria-label="Проверка сессии"
                className="flex h-screen flex-col gap-3 bg-app p-5"
            >
                <Skeleton className="h-12 w-full max-w-md" />
                <Skeleton className="h-full w-full" />
            </div>
        );
    }

    if (error || !user) {
        return <Navigate to="/login" replace state={{ from: location.pathname }} />;
    }

    return <>{children}</>;
}
