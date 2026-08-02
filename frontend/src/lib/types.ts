export interface DocumentListItem {
    id: number;
    slug: string;
    title: string;
    updated_at: string;
    search_match_source: "title" | "content" | "slug" | null;
    search_title: string | null;
    search_excerpt: string | null;
}

export interface DocumentDetail extends DocumentListItem {
    content_md: string;
    created_at: string;
}

export type WbsRole = "PM" | "BE" | "FE" | "UXR" | "UXD" | "EXPERT" | "QA" | "BA" | "MKT";

export interface WbsProgress {
    done: number;
    total: number;
}

export interface WbsTaskRef {
    id: number;
    stage_id: number;
    stage_name: string;
    due_date: string | null;
}

export interface WbsNode {
    id: number;
    code: string;
    phase_name: string | null;
    title: string;
    role: WbsRole | null;
    progress: WbsProgress | null;
    task: WbsTaskRef | null;
    children: WbsNode[];
}

export interface WbsItem {
    id: number;
    parent_id: number | null;
    code: string;
    phase_name: string | null;
    title: string;
    role: WbsRole | null;
    order_index: number;
    is_leaf: boolean;
}

export interface WbsItemCreate {
    parent_id: number | null;
    title: string;
    role?: WbsRole | null;
    phase_name?: string | null;
}

export interface WbsItemUpdate {
    title?: string;
    role?: WbsRole | null;
    phase_name?: string | null;
}

export interface KanbanStage {
    id: number;
    name: string;
    order_index: number;
    color: string;
    is_done_stage: boolean;
}

export interface KanbanTask {
    id: number;
    wbs_item_id: number | null;
    stage_id: number;
    title: string;
    description_md: string | null;
    due_date: string | null;
    position: number;
    created_at: string;
    updated_at: string;
    wbs_code: string | null;
    wbs_phase_name: string | null;
    comments_count: number;
    last_comment: string | null;
    search_match_source: "title" | "description" | "comment" | "comment_author" | "wbs_code" | null;
    search_title: string | null;
    search_excerpt: string | null;
}

export type TaskActivityEventType =
    | "STAGE_CHANGED"
    | "DUE_DATE_CHANGED"
    | "DESCRIPTION_CHANGED"
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

export interface LinkedTarget {
    link_id: number;
    kanban_task_id: number | null;
    wbs_item_id: number | null;
    title: string;
}

export interface LinkedDocument {
    link_id: number;
    document_id: number;
    slug: string;
    title: string;
}

export const ROLE_COLORS: Record<WbsRole, string> = {
    PM: "#F5B800",
    BE: "#F97316",
    FE: "#38BDF8",
    UXR: "#A855F7",
    UXD: "#EC4899",
    EXPERT: "#22C55E",
    QA: "#EF4444",
    BA: "#3B82F6",
    MKT: "#2DD4BF",
};
