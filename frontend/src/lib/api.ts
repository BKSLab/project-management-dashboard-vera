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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const isFormData = init?.body instanceof FormData;
    const response = await fetch(apiUrl(path), {
        ...init,
        headers: {
            ...(!isFormData && { "Content-Type": "application/json" }),
            ...init?.headers,
        },
    });

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

/** Единый источник правды по адресам API — маршруты не разъезжаются по экранам. */
export const endpoints = {
    dashboard: () => `${V1}/dashboard`,
    projects: () => `${V1}/projects`,
    project: (projectId: number) => `${V1}/projects/${projectId}`,
    projectStats: (projectId: number) => `${V1}/projects/${projectId}/stats`,
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
    dashboard: ["dashboard"] as const,
    projects: ["projects"] as const,
    project: (projectId: number) => ["projects", projectId] as const,
    projectStats: (projectId: number) => ["projects", projectId, "stats"] as const,
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
