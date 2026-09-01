const API_BASE_URL = import.meta.env.DEV ? "http://localhost:8000" : "";

export function apiUrl(path: string): string {
    return `${API_BASE_URL}${path}`;
}

export class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
        super(message);
        this.status = status;
    }
}

/** Слушатели, которым нужно узнать о протухшей сессии. */
const unauthorizedHandlers = new Set<() => void>();

export function onUnauthorized(handler: () => void): () => void {
    unauthorizedHandlers.add(handler);
    return () => unauthorizedHandlers.delete(handler);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const isFormData = init?.body instanceof FormData;
    const response = await fetch(apiUrl(path), {
        ...init,
        // Сессия живёт в httpOnly cookie, поэтому её нужно слать с каждым запросом.
        credentials: "include",
        headers: {
            ...(!isFormData && { "Content-Type": "application/json" }),
            ...init?.headers,
        },
    });

    if (response.status === 401) {
        // Токен протух в открытой вкладке: сообщаем приложению, чтобы увело на вход.
        for (const handler of unauthorizedHandlers) {
            handler();
        }
    }

    if (!response.ok) {
        const body = await response.json().catch(() => null);
        const message = body?.detail
            ? typeof body.detail === "string"
                ? body.detail
                : JSON.stringify(body.detail)
            : response.statusText;
        throw new ApiError(response.status, message);
    }

    if (response.status === 204) {
        return undefined as T;
    }

    return response.json() as Promise<T>;
}

export const api = {
    get: <T>(path: string) => request<T>(path),
    post: <T>(path: string, body?: unknown) =>
        request<T>(path, {
            method: "POST",
            body: body !== undefined ? JSON.stringify(body) : undefined,
        }),
    postForm: <T>(path: string, body: FormData) => request<T>(path, { method: "POST", body }),
    patch: <T>(path: string, body: unknown) =>
        request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
    delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

const V1 = "/api/v1";

export const authEndpoints = {
    register: () => `${V1}/auth/register`,
    login: () => `${V1}/auth/login`,
    logout: () => `${V1}/auth/logout`,
    me: () => `${V1}/auth/me`,
    profile: () => `${V1}/users/me`,
    password: () => `${V1}/users/me/password`,
    avatar: () => `${V1}/users/me/avatar`,
};

/** Единый источник правды по адресам API — маршруты не разъезжаются по экранам. */
export const endpoints = {
    dashboard: () => `${V1}/dashboard`,
    projects: () => `${V1}/projects`,
    project: (projectId: number) => `${V1}/projects/${projectId}`,
    projectStats: (projectId: number) => `${V1}/projects/${projectId}/stats`,
    projectKnowledgeStatus: (projectId: number) =>
        `${V1}/projects/${projectId}/knowledge/status`,
    projectKnowledgeAsk: (projectId: number) => `${V1}/projects/${projectId}/knowledge/ask`,
    projectKnowledgeReindex: (projectId: number) =>
        `${V1}/projects/${projectId}/knowledge/reindex`,
    projectStages: (projectId: number) => `${V1}/projects/${projectId}/stages`,
    stage: (stageId: number) => `${V1}/stages/${stageId}`,
    projectTasks: (projectId: number) => `${V1}/projects/${projectId}/tasks`,
    task: (taskId: number) => `${V1}/tasks/${taskId}`,
    taskMove: (taskId: number) => `${V1}/tasks/${taskId}/move`,
    taskComments: (taskId: number) => `${V1}/tasks/${taskId}/comments`,
    taskActivity: (taskId: number) => `${V1}/tasks/${taskId}/activity`,
    taskAttachments: (taskId: number) => `${V1}/tasks/${taskId}/attachments`,
    taskAttachment: (taskId: number, attachmentId: number) =>
        `${V1}/tasks/${taskId}/attachments/${attachmentId}`,
    taskLinks: (taskId: number) => `${V1}/tasks/${taskId}/links`,
    projectDocuments: (projectId: number) => `${V1}/projects/${projectId}/documents`,
    document: (documentId: number) => `${V1}/documents/${documentId}`,
    documentLinks: (documentId: number) => `${V1}/documents/${documentId}/links`,
    links: () => `${V1}/document-links`,
    link: (linkId: number) => `${V1}/document-links/${linkId}`,
    wbs: (projectId: number) => `${V1}/projects/${projectId}/wbs`,
    wbsNodes: (projectId: number) => `${V1}/projects/${projectId}/wbs/nodes`,
    wbsNode: (projectId: number, nodeId: number) => `${V1}/projects/${projectId}/wbs/nodes/${nodeId}`,
    wbsNodeMove: (projectId: number, nodeId: number) =>
        `${V1}/projects/${projectId}/wbs/nodes/${nodeId}/move`,
    wbsTaskAssign: (projectId: number, taskId: number) =>
        `${V1}/projects/${projectId}/wbs/tasks/${taskId}/assign`,
    wbsTaskAssignment: (projectId: number, taskId: number) =>
        `${V1}/projects/${projectId}/wbs/tasks/${taskId}/assignment`,
};

/** Ключи кэша TanStack Query: всё, что относится к проекту, инвалидируется вместе. */
export const queryKeys = {
    currentUser: ["auth", "me"] as const,
    dashboard: ["dashboard"] as const,
    projects: ["projects"] as const,
    project: (projectId: number) => ["projects", projectId] as const,
    projectStats: (projectId: number) => ["projects", projectId, "stats"] as const,
    projectKnowledgeStatus: (projectId: number) =>
        ["projects", projectId, "knowledge", "status"] as const,
    stages: (projectId: number) => ["projects", projectId, "stages"] as const,
    tasks: (projectId: number, search?: string) =>
        ["projects", projectId, "tasks", search ?? ""] as const,
    task: (taskId: number) => ["tasks", taskId] as const,
    taskComments: (taskId: number) => ["tasks", taskId, "comments"] as const,
    taskActivity: (taskId: number) => ["tasks", taskId, "activity"] as const,
    taskAttachments: (taskId: number) => ["tasks", taskId, "attachments"] as const,
    taskLinks: (taskId: number) => ["tasks", taskId, "links"] as const,
    documents: (projectId: number, search?: string) =>
        ["projects", projectId, "documents", search ?? ""] as const,
    document: (documentId: number) => ["documents", documentId] as const,
    documentLinks: (documentId: number) => ["documents", documentId, "links"] as const,
    wbs: (projectId: number) => ["projects", projectId, "wbs"] as const,
};
