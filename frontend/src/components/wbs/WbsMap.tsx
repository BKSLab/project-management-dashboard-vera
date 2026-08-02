import {
    useCallback,
    useDeferredValue,
    useLayoutEffect,
    useMemo,
    useRef,
    useState,
    type KeyboardEvent,
    type PointerEvent as ReactPointerEvent,
    type WheelEvent,
} from "react";
import { cn } from "@/lib/cn";
import type { KanbanStage, WbsNode, WbsRole } from "@/lib/types";
import { ROLE_COLORS } from "@/lib/types";
import {
    buildWbsMapModel,
    stageCount,
    type WbsMapLayoutNode,
    type WbsMapNodeSummary,
} from "@/lib/wbsMap";

const MIN_SCALE = 0.035;
const MAX_SCALE = 1.8;

interface Viewport {
    x: number;
    y: number;
    scale: number;
}

interface DragState {
    pointerId: number;
    clientX: number;
    clientY: number;
    originX: number;
    originY: number;
}

interface WbsMapProps {
    tree: WbsNode[];
    stages: KanbanStage[];
    onOpenTask: (taskId: number) => void;
}

function clamp(value: number, minimum: number, maximum: number): number {
    return Math.min(Math.max(value, minimum), maximum);
}

function collectExpandableIds(nodes: WbsNode[]): Set<number> {
    const ids = new Set<number>();
    function visit(node: WbsNode) {
        if (node.children.length > 0) ids.add(node.id);
        node.children.forEach(visit);
    }
    nodes.forEach(visit);
    return ids;
}

function formatDueDate(value: string): string {
    return new Date(`${value}T00:00:00`).toLocaleDateString("ru-RU", {
        day: "2-digit",
        month: "short",
    });
}

function completionPercent(summary: WbsMapNodeSummary): number {
    return summary.taskCount > 0
        ? Math.round((summary.doneCount / summary.taskCount) * 100)
        : 0;
}

function stageColor(node: WbsMapLayoutNode, stagesById: ReadonlyMap<number, KanbanStage>): string {
    if (node.task) return stagesById.get(node.task.stage_id)?.color ?? "#9CA3AF";
    if (node.taskCount > 0 && node.doneCount === node.taskCount) return "#10B981";
    if (node.sourceId === null) return "#6366F1";
    return "#475569";
}

function StageDistribution({
    summary,
    stages,
    compact = false,
}: {
    summary: WbsMapNodeSummary;
    stages: KanbanStage[];
    compact?: boolean;
}) {
    if (summary.taskCount === 0) {
        return <div className={cn("rounded-full bg-white/8", compact ? "h-1" : "h-1.5")} />;
    }
    return (
        <div
            className={cn("flex overflow-hidden rounded-full bg-white/8", compact ? "h-1" : "h-1.5")}
            aria-label={`Выполнено ${summary.doneCount} из ${summary.taskCount}`}
        >
            {stages.map((stage) => {
                const count = stageCount(summary, stage.id);
                if (count === 0) return null;
                return (
                    <span
                        key={stage.id}
                        title={`${stage.name}: ${count}`}
                        style={{
                            width: `${(count / summary.taskCount) * 100}%`,
                            backgroundColor: stage.color,
                        }}
                    />
                );
            })}
        </div>
    );
}

function RoleBadge({ role }: { role: WbsRole }) {
    const color = ROLE_COLORS[role];
    return (
        <span
            className="rounded px-1.5 py-px font-mono text-[9px] font-bold tracking-wide"
            style={{ color, backgroundColor: `${color}1A`, border: `1px solid ${color}4D` }}
        >
            {role}
        </span>
    );
}

function ProjectNodeCard({ node, stages }: { node: WbsMapLayoutNode; stages: KanbanStage[] }) {
    const percent = completionPercent(node);
    return (
        <div className="relative flex h-full flex-col overflow-hidden rounded-2xl border border-accent/70 bg-[#1a1f2e] px-4 py-3 shadow-[0_18px_45px_rgba(0,0,0,0.38)]">
            <div className="absolute inset-x-0 top-0 h-0.5 bg-accent" />
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <div className="font-mono text-[9px] font-semibold uppercase tracking-[0.18em] text-accent-secondary">
                        Интерактивная ИСР
                    </div>
                    <div className="mt-1 truncate text-[14px] font-bold text-foreground">{node.title}</div>
                </div>
                <div className="font-mono text-lg font-bold text-accent-hover">{percent}%</div>
            </div>
            <div className="mt-auto">
                <StageDistribution summary={node} stages={stages} />
                <div className="mt-1.5 flex items-center justify-between text-[9px] text-muted">
                    <span>{node.doneCount} готово</span>
                    <span>{node.taskCount} задач</span>
                </div>
            </div>
        </div>
    );
}

function TaskNodeCard({
    node,
    stage,
}: {
    node: WbsMapLayoutNode;
    stage: KanbanStage | undefined;
}) {
    const color = stage?.color ?? "#9CA3AF";
    const overdue = node.overdueCount > 0;
    return (
        <div
            className="relative flex h-full flex-col overflow-hidden rounded-xl border bg-[#202738] px-3 py-2.5 shadow-[0_7px_20px_rgba(0,0,0,0.25)] transition-colors"
            style={{ borderColor: overdue ? "#EF4444" : `${color}99` }}
        >
            <div className="absolute inset-x-0 top-0 h-1" style={{ backgroundColor: color }} />
            <div className="flex min-w-0 items-center justify-between gap-2">
                <span className="truncate font-mono text-[9px] font-semibold text-accent-secondary">
                    {node.code}
                </span>
                {node.role && <RoleBadge role={node.role} />}
            </div>
            <div className="mt-1 line-clamp-2 text-[12px] font-semibold leading-[1.3] text-foreground">
                {node.title}
            </div>
            <div className="mt-auto flex min-w-0 items-center justify-between gap-2 text-[9px]">
                <span
                    className="max-w-[130px] truncate rounded-full px-2 py-0.5 font-semibold"
                    style={{ color, backgroundColor: `${color}18` }}
                >
                    {stage?.name ?? node.task?.stage_name ?? "Без стадии"}
                </span>
                {node.task?.due_date && (
                    <span className={cn("font-mono", overdue ? "font-bold text-danger" : "text-muted")}>
                        {formatDueDate(node.task.due_date)}
                    </span>
                )}
            </div>
        </div>
    );
}

function BranchNodeCard({ node, stages }: { node: WbsMapLayoutNode; stages: KanbanStage[] }) {
    const percent = completionPercent(node);
    const completed = node.taskCount > 0 && node.doneCount === node.taskCount;
    return (
        <div
            className="relative flex h-full flex-col rounded-xl border bg-[#1a1f2e] px-3 py-2.5 shadow-[0_7px_20px_rgba(0,0,0,0.22)]"
            style={{ borderColor: completed ? "#10B98199" : "rgba(255,255,255,0.12)" }}
        >
            <div className="flex min-w-0 items-start justify-between gap-2">
                <div className="min-w-0">
                    <div className="truncate font-mono text-[9px] font-semibold text-accent-secondary">
                        {node.code}
                    </div>
                    <div className="mt-1 line-clamp-2 text-[12px] font-semibold leading-[1.3] text-foreground">
                        {node.title}
                    </div>
                </div>
                <span
                    className={cn(
                        "shrink-0 rounded-md px-1.5 py-1 font-mono text-[10px] font-bold",
                        completed ? "bg-success/15 text-success" : "bg-white/5 text-muted",
                    )}
                >
                    {percent}%
                </span>
            </div>
            <div className="mt-auto">
                <StageDistribution summary={node} stages={stages} compact />
                <div className="mt-1.5 flex items-center justify-between text-[9px] text-muted">
                    <span>{node.doneCount}/{node.taskCount} готово</span>
                    {node.hasChildren && (
                        <span className="font-semibold text-foreground">
                            {node.isExpanded ? "Свернуть −" : `Раскрыть +${node.hiddenNodeCount}`}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}

function MapNode({
    node,
    stages,
    stagesById,
    dimmed,
    selected,
    onActivate,
    onFocus,
}: {
    node: WbsMapLayoutNode;
    stages: KanbanStage[];
    stagesById: ReadonlyMap<number, KanbanStage>;
    dimmed: boolean;
    selected: boolean;
    onActivate: () => void;
    onFocus: () => void;
}) {
    const color = stageColor(node, stagesById);
    const title = node.task
        ? `${node.code} · ${node.title} · ${node.task.stage_name}`
        : `${node.title} · ${node.doneCount} из ${node.taskCount} выполнено`;
    const handleKeyDown = (event: KeyboardEvent<SVGGElement>) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onActivate();
        }
    };

    return (
        <g
            data-map-node
            role="button"
            tabIndex={0}
            aria-label={title}
            transform={`translate(${node.x} ${node.y})`}
            opacity={dimmed ? 0.17 : 1}
            className="cursor-pointer outline-none transition-opacity duration-200"
            onClick={(event) => {
                event.stopPropagation();
                onActivate();
            }}
            onKeyDown={handleKeyDown}
            onFocus={onFocus}
        >
            <title>{title}</title>
            {(selected || node.directSearchMatch) && (
                <rect
                    x={-5}
                    y={-5}
                    width={node.width + 10}
                    height={node.height + 10}
                    rx={17}
                    fill="none"
                    stroke={node.directSearchMatch ? "#06B6D4" : color}
                    strokeWidth={selected ? 2.5 : 2}
                    vectorEffect="non-scaling-stroke"
                    className="pointer-events-none"
                />
            )}
            <foreignObject width={node.width} height={node.height} className="overflow-visible">
                <div className="h-full w-full select-none">
                    {node.sourceId === null ? (
                        <ProjectNodeCard node={node} stages={stages} />
                    ) : node.task ? (
                        <TaskNodeCard node={node} stage={stagesById.get(node.task.stage_id)} />
                    ) : (
                        <BranchNodeCard node={node} stages={stages} />
                    )}
                </div>
            </foreignObject>
        </g>
    );
}

function Icon({ name }: { name: "plus" | "minus" | "fit" | "expand" | "collapse" | "target" }) {
    const paths = {
        plus: <path d="M12 5v14M5 12h14" />,
        minus: <path d="M5 12h14" />,
        fit: <><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" /><rect x="8" y="8" width="8" height="8" rx="1" /></>,
        expand: <><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" /><path d="M8 12h8M12 8v8" /></>,
        collapse: <><path d="m3 8 5-5M16 3l5 5M3 16l5 5M16 21l5-5" /><path d="M8 12h8" /></>,
        target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="2" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
    };
    return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            {paths[name]}
        </svg>
    );
}

export function WbsMap({ tree, stages, onOpenTask }: WbsMapProps) {
    const orderedStages = useMemo(
        () => [...stages].sort((a, b) => a.order_index - b.order_index),
        [stages],
    );
    const stagesById = useMemo(
        () => new Map(orderedStages.map((stage) => [stage.id, stage])),
        [orderedStages],
    );
    const [expandedNodeIds, setExpandedNodeIds] = useState<Set<number>>(() => new Set());
    const [activeRootId, setActiveRootId] = useState<number | null>(null);
    const [activeStageId, setActiveStageId] = useState<number | null>(null);
    const [search, setSearch] = useState("");
    const deferredSearch = useDeferredValue(search);
    const [searchCursor, setSearchCursor] = useState(0);
    const [selectedNodeKey, setSelectedNodeKey] = useState<string | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, scale: 1 });
    const containerRef = useRef<HTMLDivElement>(null);
    const dragRef = useRef<DragState | null>(null);

    const model = useMemo(
        () => buildWbsMapModel(tree, orderedStages, {
            expandedNodeIds,
            activeRootId,
            search: deferredSearch,
        }),
        [activeRootId, deferredSearch, expandedNodeIds, orderedStages, tree],
    );
    const nodeByKey = useMemo(
        () => new Map(model.nodes.map((node) => [node.key, node])),
        [model.nodes],
    );

    const fitMap = useCallback(() => {
        const container = containerRef.current;
        if (!container) return;
        const rect = container.getBoundingClientRect();
        const availableWidth = Math.max(rect.width - 48, 1);
        const availableHeight = Math.max(rect.height - 48, 1);
        const scale = clamp(
            Math.min(availableWidth / model.width, availableHeight / model.height),
            MIN_SCALE,
            1.15,
        );
        setViewport({
            scale,
            x: (rect.width - model.width * scale) / 2,
            y: (rect.height - model.height * scale) / 2,
        });
    }, [model.height, model.width]);

    useLayoutEffect(() => {
        const frame = requestAnimationFrame(fitMap);
        const container = containerRef.current;
        if (!container) return () => cancelAnimationFrame(frame);
        const observer = new ResizeObserver(fitMap);
        observer.observe(container);
        return () => {
            cancelAnimationFrame(frame);
            observer.disconnect();
        };
    }, [fitMap]);

    const focusNode = useCallback((nodeId: number) => {
        const node = model.nodes.find((item) => item.sourceId === nodeId);
        const container = containerRef.current;
        if (!node || !container) return;
        const rect = container.getBoundingClientRect();
        const scale = clamp(Math.max(viewport.scale, 0.82), MIN_SCALE, MAX_SCALE);
        setViewport({
            scale,
            x: rect.width / 2 - (node.x + node.width / 2) * scale,
            y: rect.height / 2 - (node.y + node.height / 2) * scale,
        });
        setSelectedNodeKey(node.key);
    }, [model.nodes, viewport.scale]);

    const zoomAtCenter = (factor: number) => {
        const container = containerRef.current;
        if (!container) return;
        const rect = container.getBoundingClientRect();
        setViewport((current) => {
            const scale = clamp(current.scale * factor, MIN_SCALE, MAX_SCALE);
            const mapX = (rect.width / 2 - current.x) / current.scale;
            const mapY = (rect.height / 2 - current.y) / current.scale;
            return {
                scale,
                x: rect.width / 2 - mapX * scale,
                y: rect.height / 2 - mapY * scale,
            };
        });
    };

    const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
        event.preventDefault();
        const rect = event.currentTarget.getBoundingClientRect();
        const pointX = event.clientX - rect.left;
        const pointY = event.clientY - rect.top;
        setViewport((current) => {
            const scale = clamp(current.scale * Math.exp(-event.deltaY * 0.0015), MIN_SCALE, MAX_SCALE);
            const mapX = (pointX - current.x) / current.scale;
            const mapY = (pointY - current.y) / current.scale;
            return {
                scale,
                x: pointX - mapX * scale,
                y: pointY - mapY * scale,
            };
        });
    };

    const handlePointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
        if (event.button !== 0 || (event.target as Element).closest("[data-map-node]")) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        dragRef.current = {
            pointerId: event.pointerId,
            clientX: event.clientX,
            clientY: event.clientY,
            originX: viewport.x,
            originY: viewport.y,
        };
        setIsDragging(true);
    };

    const handlePointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
        const drag = dragRef.current;
        if (!drag || drag.pointerId !== event.pointerId) return;
        setViewport((current) => ({
            ...current,
            x: drag.originX + event.clientX - drag.clientX,
            y: drag.originY + event.clientY - drag.clientY,
        }));
    };

    const handlePointerEnd = (event: ReactPointerEvent<SVGSVGElement>) => {
        if (dragRef.current?.pointerId !== event.pointerId) return;
        dragRef.current = null;
        setIsDragging(false);
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
        }
    };

    const toggleNode = (nodeId: number) => {
        setExpandedNodeIds((current) => {
            const next = new Set(current);
            if (next.has(nodeId)) next.delete(nodeId);
            else next.add(nodeId);
            return next;
        });
    };

    const focusNextSearchResult = () => {
        if (model.searchResults.length === 0) return;
        const index = searchCursor % model.searchResults.length;
        focusNode(model.searchResults[index].nodeId);
        setSearchCursor((index + 1) % model.searchResults.length);
    };

    const completedPercent = completionPercent(model.summary);
    const activeRootLabel = activeRootId === null
        ? "Весь проект"
        : tree.find((root) => root.id === activeRootId)?.phase_name
            ?? tree.find((root) => root.id === activeRootId)?.title
            ?? "Фаза";

    return (
        <section className="min-w-0 w-full overflow-hidden rounded-2xl border border-white/[0.08] bg-surface shadow-[var(--shadow-panel)]">
            <div className="border-b border-white/[0.06] bg-surface-elevated/80 p-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="grid min-w-0 gap-3 sm:flex sm:flex-wrap sm:items-center sm:gap-x-6 sm:gap-y-2">
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                                {activeRootLabel}
                            </div>
                            <div className="mt-1 flex items-baseline gap-2">
                                <span className="font-mono text-2xl font-bold text-foreground">{completedPercent}%</span>
                                <span className="text-xs text-muted">выполнено</span>
                            </div>
                        </div>
                        <div className="hidden h-10 w-px bg-white/8 sm:block" aria-hidden="true" />
                        <div className="grid w-full min-w-0 grid-cols-3 gap-3 border-t border-white/8 pt-3 text-xs sm:w-auto sm:gap-4 sm:border-t-0 sm:pt-0">
                            <div><span className="block font-mono text-base font-bold text-foreground">{model.summary.taskCount}</span><span className="text-muted">задач</span></div>
                            <div><span className="block font-mono text-base font-bold text-success">{model.summary.doneCount}</span><span className="text-muted">готово</span></div>
                            <div><span className={cn("block font-mono text-base font-bold", model.summary.overdueCount ? "text-danger" : "text-foreground")}>{model.summary.overdueCount}</span><span className="text-muted">просрочено</span></div>
                        </div>
                    </div>

                    <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-2 xl:max-w-3xl xl:grid-cols-[minmax(220px,1fr)_190px_180px]">
                        <div className="relative sm:col-span-2 xl:col-span-1">
                            <input
                                value={search}
                                onChange={(event) => {
                                    setSearch(event.target.value);
                                    setSearchCursor(0);
                                }}
                                onKeyDown={(event) => {
                                    if (event.key === "Enter") focusNextSearchResult();
                                }}
                                placeholder="Код, задача, роль..."
                                aria-label="Поиск по карте ИСР"
                                className="h-9 w-full rounded-md border border-border bg-background px-3 pr-20 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                            />
                            {search.trim() && (
                                <button
                                    type="button"
                                    onClick={focusNextSearchResult}
                                    disabled={model.searchResults.length === 0}
                                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded px-2 py-1 font-mono text-[10px] font-semibold text-accent-secondary hover:bg-white/5 disabled:text-muted"
                                >
                                    {model.searchResults.length} найдено
                                </button>
                            )}
                        </div>
                        <select
                            value={activeRootId ?? ""}
                            onChange={(event) => {
                                const rootId = event.target.value ? Number(event.target.value) : null;
                                setActiveRootId(rootId);
                                if (rootId !== null) {
                                    setExpandedNodeIds((current) => new Set([...current, rootId]));
                                }
                            }}
                            aria-label="Фаза проекта"
                            className="h-9 min-w-0 rounded-md border border-border bg-background px-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        >
                            <option value="">Все фазы</option>
                            {tree.map((root) => (
                                <option key={root.id} value={root.id}>{root.phase_name ?? root.title}</option>
                            ))}
                        </select>
                        <select
                            value={activeStageId ?? ""}
                            onChange={(event) => setActiveStageId(event.target.value ? Number(event.target.value) : null)}
                            aria-label="Фильтр по стадии"
                            className="h-9 min-w-0 rounded-md border border-border bg-background px-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        >
                            <option value="">Все стадии</option>
                            {orderedStages.map((stage) => (
                                <option key={stage.id} value={stage.id}>{stage.name}</option>
                            ))}
                        </select>
                    </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2" aria-label="Легенда стадий">
                    {orderedStages.map((stage) => {
                        const count = stageCount(model.summary, stage.id);
                        const active = activeStageId === stage.id;
                        return (
                            <button
                                type="button"
                                key={stage.id}
                                onClick={() => setActiveStageId(active ? null : stage.id)}
                                aria-pressed={active}
                                className={cn(
                                    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                                    active ? "border-white/25 bg-white/10 text-foreground" : "border-white/8 bg-white/[0.03] text-muted hover:border-white/15 hover:text-foreground",
                                )}
                            >
                                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: stage.color }} />
                                {stage.name}
                                <span className="font-mono opacity-70">{count}</span>
                            </button>
                        );
                    })}
                </div>
            </div>

            <div className="relative">
                <div
                    ref={containerRef}
                    className="relative h-[68dvh] min-h-[560px] max-h-[880px] w-full overflow-hidden bg-[#111827]"
                >
                    <svg
                        className={cn("h-full w-full touch-none", isDragging ? "cursor-grabbing" : "cursor-grab")}
                        role="img"
                        aria-label="Интерактивная карта иерархической структуры работ"
                        onWheel={handleWheel}
                        onPointerDown={handlePointerDown}
                        onPointerMove={handlePointerMove}
                        onPointerUp={handlePointerEnd}
                        onPointerCancel={handlePointerEnd}
                    >
                        <defs>
                            <pattern id="wbs-map-grid-small" width="24" height="24" patternUnits="userSpaceOnUse">
                                <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(255,255,255,0.025)" strokeWidth="1" />
                            </pattern>
                            <pattern id="wbs-map-grid" width="120" height="120" patternUnits="userSpaceOnUse">
                                <rect width="120" height="120" fill="url(#wbs-map-grid-small)" />
                                <path d="M 120 0 L 0 0 0 120" fill="none" stroke="rgba(99,102,241,0.07)" strokeWidth="1" />
                            </pattern>
                        </defs>
                        <rect width="100%" height="100%" fill="url(#wbs-map-grid)" />
                        <g transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`}>
                            {model.edges.map((edge) => {
                                const target = nodeByKey.get(edge.targetKey);
                                const controlOffset = Math.max((edge.targetY - edge.sourceY) * 0.48, 30);
                                const dimmed = Boolean(
                                    target
                                    && (
                                        (activeStageId !== null && stageCount(target, activeStageId) === 0)
                                        || (deferredSearch.trim() && !target.containsSearchMatch)
                                    )
                                );
                                return (
                                    <path
                                        key={edge.key}
                                        d={`M ${edge.sourceX} ${edge.sourceY} C ${edge.sourceX} ${edge.sourceY + controlOffset}, ${edge.targetX} ${edge.targetY - controlOffset}, ${edge.targetX} ${edge.targetY}`}
                                        fill="none"
                                        stroke={target ? stageColor(target, stagesById) : "#475569"}
                                        strokeOpacity={dimmed ? 0.08 : 0.42}
                                        strokeWidth={target?.task ? 2 : 1.4}
                                        vectorEffect="non-scaling-stroke"
                                    />
                                );
                            })}
                            {model.nodes.map((node) => {
                                const dimmed = (
                                    activeStageId !== null && stageCount(node, activeStageId) === 0
                                ) || Boolean(deferredSearch.trim() && node.sourceId !== null && !node.containsSearchMatch);
                                return (
                                    <MapNode
                                        key={node.key}
                                        node={node}
                                        stages={orderedStages}
                                        stagesById={stagesById}
                                        dimmed={dimmed}
                                        selected={selectedNodeKey === node.key}
                                        onFocus={() => setSelectedNodeKey(node.key)}
                                        onActivate={() => {
                                            setSelectedNodeKey(node.key);
                                            if (node.task) onOpenTask(node.task.id);
                                            else if (node.sourceId !== null && node.hasChildren) toggleNode(node.sourceId);
                                        }}
                                    />
                                );
                            })}
                        </g>
                    </svg>

                    <div className="absolute left-3 top-3 flex overflow-hidden rounded-lg border border-white/10 bg-surface/90 shadow-[var(--shadow-card)] backdrop-blur-md">
                        <button type="button" onClick={() => zoomAtCenter(1.22)} aria-label="Приблизить карту" className="border-r border-white/8 p-2 text-muted hover:bg-white/8 hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent"><Icon name="plus" /></button>
                        <button type="button" onClick={() => zoomAtCenter(1 / 1.22)} aria-label="Отдалить карту" className="border-r border-white/8 p-2 text-muted hover:bg-white/8 hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent"><Icon name="minus" /></button>
                        <button type="button" onClick={fitMap} aria-label="Вписать карту в экран" className="p-2 text-muted hover:bg-white/8 hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent"><Icon name="fit" /></button>
                    </div>

                    <div className="absolute right-3 top-3 flex flex-col gap-2 sm:flex-row">
                        <button
                            type="button"
                            onClick={() => setExpandedNodeIds(collectExpandableIds(tree))}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-surface/90 px-2.5 py-2 text-[11px] font-semibold text-muted shadow-[var(--shadow-card)] backdrop-blur-md hover:bg-surface-hover hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        >
                            <Icon name="expand" /> Все задачи
                        </button>
                        <button
                            type="button"
                            onClick={() => setExpandedNodeIds(new Set())}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-surface/90 px-2.5 py-2 text-[11px] font-semibold text-muted shadow-[var(--shadow-card)] backdrop-blur-md hover:bg-surface-hover hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        >
                            <Icon name="collapse" /> Обзор
                        </button>
                    </div>

                    {model.searchResults.length > 0 && search.trim() && (
                        <button
                            type="button"
                            onClick={focusNextSearchResult}
                            className="absolute bottom-3 left-1/2 inline-flex -translate-x-1/2 items-center gap-2 rounded-full border border-accent-secondary/30 bg-surface/95 px-4 py-2 text-xs font-semibold text-foreground shadow-[var(--shadow-panel)] backdrop-blur-md hover:border-accent-secondary/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        >
                            <Icon name="target" /> Перейти к совпадению
                        </button>
                    )}

                    <div className="pointer-events-none absolute bottom-3 right-3 rounded-lg border border-white/8 bg-surface/85 px-2.5 py-1.5 font-mono text-[10px] text-muted backdrop-blur-md">
                        {model.visibleNodeCount}/{model.totalNodeCount} узлов · {Math.round(viewport.scale * 100)}%
                    </div>
                </div>
                <div className="flex flex-col gap-1 border-t border-white/[0.06] bg-surface-elevated/60 px-4 py-2 text-[11px] text-muted sm:flex-row sm:items-center sm:justify-between">
                    <span>Колесо — масштаб · перетаскивание — навигация · клик — раскрыть ветку или открыть задачу</span>
                    <span className="font-mono text-accent-secondary">Цвет = стадия канбана</span>
                </div>
            </div>
        </section>
    );
}
