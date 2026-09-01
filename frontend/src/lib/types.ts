export interface User {
    id: number;
    username: string;
    last_name: string;
    first_name: string;
    middle_name: string | null;
    email: string | null;
    phone: string | null;
    telegram: string | null;
    has_avatar: boolean;
    created_at: string;
}

export interface RegisterPayload {
    username: string;
    password: string;
    password_confirm: string;
    last_name: string;
    first_name: string;
    middle_name?: string | null;
    email?: string | null;
    phone?: string | null;
    telegram?: string | null;
    invite_code: string;
}

export interface LoginPayload {
    username: string;
    password: string;
}

export interface UserUpdatePayload {
    last_name?: string;
    first_name?: string;
    middle_name?: string | null;
    email?: string | null;
    phone?: string | null;
    telegram?: string | null;
}

export interface PasswordChangePayload {
    current_password: string;
    password: string;
    password_confirm: string;
}

export type ProjectStatus = "PLANNING" | "ACTIVE" | "PAUSED" | "COMPLETED" | "ARCHIVED";

export type TaskPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export type TaskRole = "PM" | "BE" | "FE" | "UXR" | "UXD" | "EXPERT" | "QA" | "BA" | "MKT";

export interface Project {
    id: number;
    key: string;
    name: string;
    description_md: string | null;
    status: ProjectStatus;
    color: string;
    icon: string | null;
    start_date: string | null;
    due_date: string | null;
    order_index: number;
    created_at: string;
    updated_at: string;
}

export interface ProjectCreate {
    key: string;
    name: string;
    description_md?: string | null;
    status?: ProjectStatus;
    color?: string;
    icon?: string | null;
    start_date?: string | null;
    due_date?: string | null;
}

export type ProjectUpdate = Partial<ProjectCreate> & { order_index?: number };

export interface StageBreakdown {
    stage_id: number;
    stage_name: string;
    color: string;
    is_done_stage: boolean;
    tasks_count: number;
}

export interface ProjectStats {
    project_id: number;
    total_tasks: number;
    done_tasks: number;
    in_progress_tasks: number;
    overdue_tasks: number;
    due_soon_tasks: number;
    unassigned_tasks: number;
    completion_rate: number;
    next_due_date: string | null;
    stage_breakdown: StageBreakdown[];
}

export interface ProjectStage {
    id: number;
    project_id: number;
    name: string;
    order_index: number;
    color: string;
    is_done_stage: boolean;
}

export interface StageCreate {
    name: string;
    color?: string;
    is_done_stage?: boolean;
}

export interface StageUpdate {
    name?: string;
    color?: string;
    order_index?: number;
    is_done_stage?: boolean;
}

export type SearchMatchSource =
    | "title"
    | "description"
    | "comment"
    | "comment_author"
    | "content"
    | "slug"
    | null;

export interface Task {
    id: number;
    project_id: number;
    stage_id: number;
    wbs_node_id: number | null;
    number: number;
    key: string;
    title: string;
    description_md: string | null;
    priority: TaskPriority;
    role: TaskRole | null;
    assignee: string | null;
    due_date: string | null;
    position: number;
    created_at: string;
    updated_at: string;
    comments_count: number;
    last_comment: string | null;
    search_match_source: SearchMatchSource;
    search_title: string | null;
    search_excerpt: string | null;
}

export interface TaskCompact {
    id: number;
    key: string;
    title: string;
    stage_id: number;
    wbs_node_id: number | null;
    priority: TaskPriority;
    assignee: string | null;
    due_date: string | null;
    is_done: boolean;
}

export interface TaskCreate {
    title: string;
    description_md?: string | null;
    stage_id?: number | null;
    wbs_node_id?: number | null;
    priority?: TaskPriority;
    role?: TaskRole | null;
    assignee?: string | null;
    due_date?: string | null;
}

export interface TaskUpdate {
    title?: string;
    description_md?: string | null;
    priority?: TaskPriority;
    role?: TaskRole | null;
    assignee?: string | null;
    due_date?: string | null;
}

export type TaskActivityEventType =
    | "STAGE_CHANGED"
    | "DUE_DATE_CHANGED"
    | "DESCRIPTION_CHANGED"
    | "PRIORITY_CHANGED"
    | "ASSIGNEE_CHANGED"
    | "WBS_NODE_CHANGED"
    | "COMMENT_ADDED";

export interface TaskActivity {
    id: number;
    task_id: number;
    event_type: TaskActivityEventType;
    from_value: string | null;
    to_value: string | null;
    created_at: string;
}

export interface TaskComment {
    id: number;
    task_id: number;
    author_name: string | null;
    body_md: string;
    created_at: string;
}

export interface TaskAttachment {
    id: number;
    task_id: number;
    original_name: string;
    content_type: string;
    size: number;
    created_at: string;
    content_url: string;
    previewable: boolean;
}

export interface WbsNode {
    id: number;
    project_id: number;
    parent_id: number | null;
    title: string;
    position: number;
    created_at: string;
    updated_at: string;
}

export interface WbsStats {
    total_nodes: number;
    total_tasks: number;
    assigned_tasks: number;
    unassigned_tasks: number;
    done_tasks: number;
    overdue_tasks: number;
}

export interface WbsStructure {
    nodes: WbsNode[];
    tasks: TaskCompact[];
    stats: WbsStats;
}

export interface WbsNodeDeleteResult {
    deleted_nodes: number;
    released_tasks: number;
}

export interface DocumentListItem {
    id: number;
    project_id: number;
    slug: string;
    title: string;
    updated_at: string;
    search_match_source: SearchMatchSource;
    search_title: string | null;
    search_excerpt: string | null;
}

export interface DocumentDetail extends DocumentListItem {
    content_md: string;
    created_at: string;
}

export interface LinkedDocument {
    link_id: number;
    document_id: number;
    slug: string;
    title: string;
}

export interface LinkedTask {
    link_id: number;
    task_id: number;
    key: string;
    title: string;
}

export interface DashboardTotals {
    total_projects: number;
    active_projects: number;
    total_tasks: number;
    done_tasks: number;
    in_progress_tasks: number;
    overdue_tasks: number;
    completion_rate: number;
}

export interface DashboardProject {
    id: number;
    key: string;
    name: string;
    description_md: string | null;
    status: ProjectStatus;
    color: string;
    icon: string | null;
    total_tasks: number;
    done_tasks: number;
    in_progress_tasks: number;
    overdue_tasks: number;
    completion_rate: number;
    next_due_date: string | null;
    updated_at: string;
}

export interface DashboardTask {
    id: number;
    key: string;
    title: string;
    project_id: number;
    project_key: string;
    project_name: string;
    project_color: string;
    stage_id: number;
    stage_name: string;
    priority: TaskPriority;
    due_date: string | null;
    is_overdue: boolean;
    updated_at: string;
}

export interface Dashboard {
    totals: DashboardTotals;
    projects: DashboardProject[];
    attention_tasks: DashboardTask[];
    recent_tasks: DashboardTask[];
}

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
    PLANNING: "Планирование",
    ACTIVE: "В работе",
    PAUSED: "На паузе",
    COMPLETED: "Завершён",
    ARCHIVED: "В архиве",
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
    LOW: "Низкий",
    MEDIUM: "Средний",
    HIGH: "Высокий",
    URGENT: "Срочный",
};

export const PRIORITY_ORDER: TaskPriority[] = ["URGENT", "HIGH", "MEDIUM", "LOW"];

export const ROLE_LABELS: Record<TaskRole, string> = {
    PM: "Менеджер проекта",
    BE: "Backend",
    FE: "Frontend",
    UXR: "UX-исследования",
    UXD: "UX-дизайн",
    EXPERT: "Эксперт",
    QA: "Тестирование",
    BA: "Аналитика",
    MKT: "Маркетинг",
};

/** Полное имя: отчество есть не у всех, поэтому склеиваем через фильтр. */
export function fullName(user: User): string {
    return [user.last_name, user.first_name, user.middle_name].filter(Boolean).join(" ");
}

/** Инициалы для аватара-заглушки. */
export function initials(user: User): string {
    return `${user.last_name.charAt(0)}${user.first_name.charAt(0)}`.toUpperCase();
}

export const PROJECT_COLORS = [
    "#58a6ff",
    "#a371f7",
    "#3fb950",
    "#d29922",
    "#f85149",
    "#39c5cf",
    "#db61a2",
    "#7d8793",
];
