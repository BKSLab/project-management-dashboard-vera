import { useDraggable } from "@dnd-kit/core";
import type { KanbanTask } from "@/lib/types";
import { cn } from "@/lib/cn";
import { SearchHighlight } from "@/components/ui/SearchHighlight";

interface TaskCardProps {
    task: KanbanTask;
    highlighted?: boolean;
    onClick: () => void;
}

function dueDateState(dueDate: string | null): "overdue" | "soon" | "normal" | null {
    if (!dueDate) return null;
    const today = new Date(new Date().toDateString());
    const due = new Date(dueDate);
    const diffDays = (due.getTime() - today.getTime()) / 86_400_000;
    if (diffDays < 0) return "overdue";
    if (diffDays <= 3) return "soon";
    return "normal";
}

const DUE_DATE_COLOR: Record<"overdue" | "soon" | "normal", string> = {
    overdue: "text-danger",
    soon: "text-warning",
    normal: "text-muted",
};

interface TaskCardContentProps {
    task: KanbanTask;
}

const SEARCH_SOURCE_LABEL: Partial<Record<NonNullable<KanbanTask["search_match_source"]>, string>> = {
    description: "В описании",
    comment: "В комментарии",
    comment_author: "Автор комментария",
};

/** Внутренняя разметка карточки — переиспользуется в DragOverlay (там нет dnd-kit-хуков). */
export function TaskCardContent({ task }: TaskCardContentProps) {
    const dueState = dueDateState(task.due_date);

    return (
        <>
            <p className="font-mono text-xs text-muted">TASK-{task.id}</p>

            <p className="mt-1 line-clamp-2 text-[15px] font-semibold text-foreground">
                <SearchHighlight text={task.search_title ?? task.title} />
            </p>

            {task.search_excerpt && task.search_match_source !== "wbs_code" ? (
                <p className="mt-2 line-clamp-2 rounded-lg bg-accent/[0.07] px-2 py-1.5 text-xs leading-[1.45] text-[#cbd5e1] ring-1 ring-inset ring-accent/15">
                    {SEARCH_SOURCE_LABEL[task.search_match_source ?? "title"] && (
                        <span className="mr-1 font-semibold text-accent-secondary">
                            {SEARCH_SOURCE_LABEL[task.search_match_source ?? "title"]}:
                        </span>
                    )}
                    <SearchHighlight text={task.search_excerpt} />
                </p>
            ) : task.description_md ? (
                <p className="mt-1 line-clamp-2 text-[13px] leading-[1.4] text-muted">
                    {task.description_md}
                </p>
            ) : null}

            {task.last_comment && !task.search_excerpt && (
                <p className="mt-2 line-clamp-1 rounded-lg bg-white/[0.03] px-2 py-1 text-xs text-[#cbd5e1]">
                    💬 {task.last_comment}
                </p>
            )}

            <div className="mt-2 flex items-center gap-3 text-xs text-muted">
                {task.wbs_code && (
                    <span className="font-mono text-accent-secondary">
                        <SearchHighlight
                            text={
                                task.search_match_source === "wbs_code" && task.search_excerpt
                                    ? task.search_excerpt
                                    : task.wbs_code
                            }
                        />
                    </span>
                )}
                {task.due_date && (
                    <span className={dueState ? DUE_DATE_COLOR[dueState] : undefined}>
                        {new Date(task.due_date).toLocaleDateString("ru-RU")}
                    </span>
                )}
                {task.comments_count > 0 && <span>💬 {task.comments_count}</span>}
            </div>
        </>
    );
}

const STATIC_CARD_CLASS =
    "block w-full cursor-pointer rounded-xl border border-white/[0.05] bg-surface-elevated p-3 text-left text-sm shadow-[var(--shadow-card)] transition-[transform,box-shadow,border-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-white/10 hover:shadow-[var(--shadow-card-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

/** Карточка без drag&drop — для превью задач вне канбана (главная страница). */
export function StaticTaskCard({ task, onClick }: { task: KanbanTask; onClick: () => void }) {
    return (
        <button type="button" onClick={onClick} className={STATIC_CARD_CLASS}>
            <TaskCardContent task={task} />
        </button>
    );
}

export function TaskCard({ task, highlighted, onClick }: TaskCardProps) {
    const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
        id: task.id,
    });

    return (
        <div
            ref={setNodeRef}
            {...attributes}
            {...listeners}
            onClick={onClick}
            className={cn(
                "cursor-pointer rounded-xl border border-white/[0.05] bg-surface-elevated p-3 text-sm shadow-[var(--shadow-card)] transition-[transform,box-shadow,border-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-white/10 hover:shadow-[var(--shadow-card-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                isDragging && "opacity-40",
                highlighted && "shadow-[var(--shadow-selected)] border-accent"
            )}
        >
            <TaskCardContent task={task} />
        </div>
    );
}
