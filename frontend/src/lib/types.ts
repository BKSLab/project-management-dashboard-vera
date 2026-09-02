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

/** Регистрация собирает минимум: остальное заполняется в профиле. */
export interface RegisterPayload {
    username: string;
    password: string;
    password_confirm: string;
    last_name: string;
    first_name: string;
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
    start_date: string | null;
    due_date: string | null;
    baseline_start_date: string | null;
    baseline_due_date: string | null;
    completed_at: string | null;
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
    start_date: string | null;
    due_date: string | null;
    is_done: boolean;
}

export interface CalendarRange {
    date_from: string;
    date_to: string;
    today: string;
}

export interface CalendarProject {
    start_date: string | null;
    due_date: string | null;
}

export interface CalendarStage {
    id: number;
    name: string;
    color: string;
    order_index: number;
    is_done_stage: boolean;
}

export interface CalendarWbsNode {
    id: number;
    parent_id: number | null;
    title: string;
    position: number;
}

export interface CalendarTask {
    id: number;
    key: string;
    title: string;
    start_date: string | null;
    due_date: string | null;
    baseline_start_date: string | null;
    baseline_due_date: string | null;
    drift_days: number | null;
    stage_id: number;
    wbs_node_id: number | null;
    priority: TaskPriority;
    assignee: string | null;
    is_done: boolean;
    is_overdue: boolean;
    is_due_soon: boolean;
    risk_level: "low" | "medium" | "high" | null;
    risk_reasons: CalendarRiskReason[];
    updated_at: string;
}

export interface CalendarRiskReason {
    code: string;
    message: string;
    days: number | null;
    task_key?: string | null;
    milestone_title?: string | null;
}

export interface CalendarDateChange {
    id: number;
    task_id: number;
    task_key: string;
    task_title: string;
    from_date: string | null;
    to_date: string | null;
    changed_at: string;
}

export interface CalendarSummary {
    overdue: number;
    due_soon: number;
    unscheduled: number;
    drifted: number;
    dependency_risks: number;
}

export interface TaskDependency {
    id: number;
    project_id: number;
    predecessor_task_id: number;
    successor_task_id: number;
    dependency_type: "FINISH_TO_START";
    lag_days: number;
    created_at: string;
}

export interface TaskDependencyInput {
    predecessor_task_id: number;
    successor_task_id: number;
    dependency_type: "FINISH_TO_START";
    lag_days: number;
}

export interface ScenarioTaskDates {
    start_date: string | null;
    due_date: string | null;
}

export interface ScenarioChangeInput extends ScenarioTaskDates {
    task_id: number;
}

export interface ScenarioNormalizedChange {
    task_id: number;
    task_key: string;
    task_title: string;
    current: ScenarioTaskDates;
    proposed: ScenarioTaskDates;
    expected_updated_at: string;
    source: "DIRECT" | "CASCADE";
    reasons: CalendarRiskReason[];
}

export interface ScenarioConflict {
    code: string;
    message: string;
    task_id: number;
    task_key: string;
}

export interface ScenarioPreview {
    changes: ScenarioNormalizedChange[];
    conflicts: ScenarioConflict[];
    consequences_count: number;
    can_apply: boolean;
}

export interface ScenarioApplyResult {
    applied_count: number;
    task_ids: number[];
}

export type ProjectMilestoneStatus = "PLANNED" | "ACHIEVED";

export interface ProjectMilestone {
    id: number;
    project_id: number;
    title: string;
    due_date: string;
    status: ProjectMilestoneStatus;
    wbs_node_id: number | null;
    description_md: string | null;
    created_at: string;
    updated_at: string;
}

export interface ProjectMilestoneInput {
    title: string;
    due_date: string;
    status: ProjectMilestoneStatus;
    wbs_node_id: number | null;
    description_md: string | null;
}

export interface CalendarMilestone {
    id: number | null;
    title: string;
    due_date: string;
    status: ProjectMilestoneStatus;
    wbs_node_id: number | null;
    description_md: string | null;
    is_system: boolean;
}

export interface ProjectCalendar {
    range: CalendarRange;
    project: CalendarProject;
    tasks: CalendarTask[];
    stages: CalendarStage[];
    wbs_nodes: CalendarWbsNode[];
    assignees: string[];
    summary: CalendarSummary;
    recent_changes: CalendarDateChange[];
    milestones: CalendarMilestone[];
    dependencies: TaskDependency[];
}

export interface UnscheduledTasksPage {
    items: CalendarTask[];
    next_cursor: number | null;
}

export interface TaskCreate {
    title: string;
    description_md?: string | null;
    stage_id?: number | null;
    wbs_node_id?: number | null;
    priority?: TaskPriority;
    role?: TaskRole | null;
    assignee?: string | null;
    start_date?: string | null;
    due_date?: string | null;
}

export interface TaskUpdate {
    title?: string;
    description_md?: string | null;
    priority?: TaskPriority;
    role?: TaskRole | null;
    assignee?: string | null;
    start_date?: string | null;
    due_date?: string | null;
}

export type TaskActivityEventType =
    | "STAGE_CHANGED"
    | "DUE_DATE_CHANGED"
    | "START_DATE_CHANGED"
    | "BASELINE_CHANGED"
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

export type KnowledgeEntityType =
    | "project"
    | "task"
    | "document"
    | "comment"
    | "attachment"
    | "milestone";

export interface KnowledgeSource {
    source_id: string;
    entity_type: KnowledgeEntityType;
    entity_id: number;
    title: string;
    excerpt: string | null;
    score: number | null;
    task_id: number | null;
    document_slug: string | null;
}

export interface KnowledgeAnswer {
    answer: string;
    sources: KnowledgeSource[];
}

export interface KnowledgeStatus {
    enabled: boolean;
    ready: boolean;
    points_count: number | null;
    pending_jobs: number;
    processing_jobs: number;
    failed_jobs: number;
    last_error: string | null;
}

export interface KnowledgeChatMessage {
    role: "user" | "assistant";
    content: string;
}

export interface KnowledgeAskPayload {
    question: string;
    history: KnowledgeChatMessage[];
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

export type ApiTokenScope = "READ" | "WRITE";

export interface ApiToken {
    id: number;
    name: string;
    prefix: string;
    scope: ApiTokenScope;
    created_at: string;
    expires_at: string | null;
    revoked_at: string | null;
    last_used_at: string | null;
}

export interface ApiTokenCreatePayload {
    name: string;
    scope: ApiTokenScope;
    ttl_days: number | null;
}

export interface ApiTokenCreated {
    token: ApiToken;
    secret: string;
}
