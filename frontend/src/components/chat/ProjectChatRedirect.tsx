import { Navigate, useLocation } from "react-router-dom";

/** Старые адреса чата сохраняют контекст задачи, диалога и подтверждения. */
export function ProjectChatRedirect({ view }: { view: "personal" | "knowledge" }) {
    const location = useLocation();
    const params = new URLSearchParams(location.search);
    params.set("view", view);
    return <Navigate to={{ pathname: "../chat", search: `?${params}`, hash: location.hash }} replace />;
}
