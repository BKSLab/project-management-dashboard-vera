import type { ProjectMember, Task, UserSummary } from "@/lib/types";
import { fullName, initials } from "@/lib/types";

export type ProjectStickerColor = "neutral" | "yellow" | "blue" | "green" | "red" | "violet";

export interface ProjectSticker {
    id: number;
    project_id: number;
    body: string;
    color: ProjectStickerColor;
    canvas_x: number;
    canvas_y: number;
    created_by_user_id: number | null;
    created_by_username_snapshot: string;
    created_by_display_name_snapshot: string;
    task_ids: number[];
    revision: number;
    created_at: string;
    updated_at: string;
}

export interface ProjectStickerInput {
    body: string;
    color: ProjectStickerColor;
    task_ids: number[];
}

export interface ProjectStickerPositionInput {
    canvas_x: number;
    canvas_y: number;
}

export type ProjectStickerCreateInput = ProjectStickerInput & ProjectStickerPositionInput;

export interface ProjectStickerUpdateInput extends ProjectStickerInput {
    revision: number;
}

export interface StickerColorOption {
    value: ProjectStickerColor;
    label: string;
}

export const STICKER_COLOR_OPTIONS: StickerColorOption[] = [
    { value: "neutral", label: "Нейтральный" },
    { value: "yellow", label: "Жёлтый" },
    { value: "blue", label: "Синий" },
    { value: "green", label: "Зелёный" },
    { value: "red", label: "Красный" },
    { value: "violet", label: "Фиолетовый" },
];

export const STICKER_TASK_RESULTS_LIMIT = 5;
export const STICKER_NODE_WIDTH = 230;
export const STICKER_NODE_HEIGHT = 230;
export const STICKER_NODE_GAP = 28;
const MAX_STICKER_COORDINATE = 1_000_000;

export interface ResolvedStickerAuthor {
    kind: "current" | "former" | "missing";
    displayName: string;
    username: string | null;
    initials: string;
    user: UserSummary | null;
}

function snapshotInitials(displayName: string, username: string): string {
    const parts = displayName.trim().split(/\s+/).filter(Boolean);
    const value = parts.length >= 2
        ? `${parts[0][0]}${parts[1][0]}`
        : parts[0]?.slice(0, 2) || username.slice(0, 2) || "?";
    return value.toUpperCase();
}

/** Актуальная команда — основной источник профиля; snapshot остаётся fallback. */
export function resolveStickerAuthor(
    sticker: ProjectSticker,
    members: ProjectMember[],
): ResolvedStickerAuthor {
    const member = sticker.created_by_user_id === null
        ? undefined
        : members.find((item) => item.user.id === sticker.created_by_user_id);
    if (member) {
        return {
            kind: "current",
            displayName: fullName(member.user),
            username: member.user.username,
            initials: initials(member.user),
            user: member.user,
        };
    }

    const displayName = sticker.created_by_display_name_snapshot.trim();
    const username = sticker.created_by_username_snapshot.trim();
    if (displayName || username) {
        return {
            kind: "former",
            displayName: displayName || username,
            username: username || null,
            initials: snapshotInitials(displayName, username),
            user: null,
        };
    }

    return {
        kind: "missing",
        displayName: "Автор не указан",
        username: null,
        initials: "?",
        user: null,
    };
}

export function stickerAuthorLabel(author: ResolvedStickerAuthor): string {
    if (author.kind === "missing") return author.displayName;
    const login = author.username ? ` · @${author.username}` : "";
    const former = author.kind === "former" ? " · бывший участник" : "";
    return `Создал: ${author.displayName}${login}${former}`;
}

/** Диалог остаётся компактным независимо от общего числа задач проекта. */
export function limitStickerTaskResults(tasks: Task[]): Task[] {
    return tasks.slice(0, STICKER_TASK_RESULTS_LIMIT);
}

function normalizeTaskSearchValue(value: string): string {
    return value.normalize("NFKC").toLocaleLowerCase("ru-RU").replaceAll("ё", "е");
}

/**
 * Короткий запрос ищем локально: PostgreSQL FTS не даёт префиксных
 * совпадений для одного-двух символов, а в task picker отклик нужен сразу.
 */
export function searchStickerTasks(tasks: Task[], query: string): Task[] {
    const terms = normalizeTaskSearchValue(query).trim().split(/\s+/).filter(Boolean);
    if (terms.length === 0) return tasks;

    return tasks.filter((task) => {
        const searchable = normalizeTaskSearchValue([
            task.key,
            task.title,
            task.description_md,
            task.last_comment,
            task.assignee,
        ].filter((value): value is string => Boolean(value)).join(" "));
        return terms.every((term) => searchable.includes(term));
    });
}

/** Объединяет мгновенные локальные и более полные серверные результаты. */
export function mergeStickerTaskResults(...groups: Task[][]): Task[] {
    const seen = new Set<number>();
    const merged: Task[] = [];
    groups.forEach((tasks) => {
        tasks.forEach((task) => {
            if (seen.has(task.id)) return;
            seen.add(task.id);
            merged.push(task);
        });
    });
    return merged;
}

function clampStickerCoordinate(value: number): number {
    const finite = Number.isFinite(value) ? value : 0;
    return Math.max(
        -MAX_STICKER_COORDINATE,
        Math.min(MAX_STICKER_COORDINATE, Math.round(finite * 10) / 10),
    );
}

/** Приводит координаты React Flow к компактному и допустимому API-формату. */
export function normalizeStickerPosition(position: {
    x: number;
    y: number;
}): ProjectStickerPositionInput {
    return {
        canvas_x: clampStickerCoordinate(position.x),
        canvas_y: clampStickerCoordinate(position.y),
    };
}

function positionsOverlap(
    candidate: ProjectStickerPositionInput,
    sticker: ProjectSticker,
): boolean {
    return candidate.canvas_x < sticker.canvas_x + STICKER_NODE_WIDTH + STICKER_NODE_GAP
        && candidate.canvas_x + STICKER_NODE_WIDTH + STICKER_NODE_GAP > sticker.canvas_x
        && candidate.canvas_y < sticker.canvas_y + STICKER_NODE_HEIGHT + STICKER_NODE_GAP
        && candidate.canvas_y + STICKER_NODE_HEIGHT + STICKER_NODE_GAP > sticker.canvas_y;
}

/** Находит рядом с центром viewport свободное место для нового стикера. */
export function findAvailableStickerPosition(
    stickers: ProjectSticker[],
    origin: { x: number; y: number },
): ProjectStickerPositionInput {
    const stepX = STICKER_NODE_WIDTH + STICKER_NODE_GAP;
    const stepY = STICKER_NODE_HEIGHT + STICKER_NODE_GAP;
    const maxRing = Math.ceil(Math.sqrt(stickers.length + 1)) + 3;

    for (let ring = 0; ring <= maxRing; ring += 1) {
        for (let row = -ring; row <= ring; row += 1) {
            for (let column = -ring; column <= ring; column += 1) {
                if (Math.max(Math.abs(column), Math.abs(row)) !== ring) continue;
                const candidate = normalizeStickerPosition({
                    x: origin.x + column * stepX,
                    y: origin.y + row * stepY,
                });
                if (!stickers.some((sticker) => positionsOverlap(candidate, sticker))) {
                    return candidate;
                }
            }
        }
    }

    return normalizeStickerPosition({
        x: origin.x + (stickers.length + 1) * stepX,
        y: origin.y,
    });
}

export function normalizeStickerInput(input: ProjectStickerInput): ProjectStickerInput {
    return {
        body: input.body.trim(),
        color: input.color,
        task_ids: [...new Set(input.task_ids)],
    };
}

export function stickerHasChanges(
    sticker: ProjectSticker,
    input: ProjectStickerInput,
): boolean {
    const normalized = normalizeStickerInput(input);
    const previousTasks = [...sticker.task_ids].sort((left, right) => left - right);
    const nextTasks = [...normalized.task_ids].sort((left, right) => left - right);
    return sticker.body !== normalized.body
        || sticker.color !== normalized.color
        || previousTasks.length !== nextTasks.length
        || previousTasks.some((taskId, index) => taskId !== nextTasks[index]);
}
