import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    Background,
    BackgroundVariant,
    Controls,
    MiniMap,
    ReactFlow,
    ReactFlowProvider,
    useReactFlow,
    type Edge,
    type Node,
    type NodeMouseHandler,
    type OnNodeDrag,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Maximize2, Network, Plus, Search } from "lucide-react";
import { cn } from "@/lib/cn";
import type { Project, ProjectStage, TaskCompact, WbsNode } from "@/lib/types";
import { dueTone } from "@/lib/dates";
import {
    buildWbsGraph,
    layoutWbsGraph,
    parseGraphNodeId,
    sectionNodeId,
    taskNodeId,
    type WbsLayoutMode,
} from "@/lib/wbsLayout";
import {
    buildWbsTree,
    collectAncestorIds,
    collectSubtreeIds,
    flattenTree,
    resolveSectionDrop,
    type SectionDropZone,
    type WbsTreeNode,
} from "@/lib/wbsTree";
import { TASK_DRAG_TYPE } from "@/components/wbs/TaskPool";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/States";
import { ProjectNode } from "@/components/wbs/nodes/ProjectNode";
import { SectionNode } from "@/components/wbs/nodes/SectionNode";
import { TaskNode } from "@/components/wbs/nodes/TaskNode";

/** Пороги semantic zoom (§34 ТЗ): подобраны так, чтобы текст оставался читаемым. */
const DETAIL_FULL_ZOOM = 0.75;
const DETAIL_COMPACT_ZOOM = 0.45;
/** Раскладка успевает пересчитаться до того, как мы центрируем результат поиска. */
const FOCUS_DELAY_MS = 280;

const NODE_TYPES = { project: ProjectNode, section: SectionNode, task: TaskNode };

/** React Flow отдаёт мышь или касание — берём координаты указателя из любого. */
function pointerPosition(event: MouseEvent | TouchEvent): { x: number; y: number } | null {
    if ("clientX" in event) {
        return { x: event.clientX, y: event.clientY };
    }
    const touch = event.changedTouches[0] ?? event.touches[0];
    return touch === undefined ? null : { x: touch.clientX, y: touch.clientY };
}

interface SectionDropState {
    movedId: number;
    targetId: number;
    zone: SectionDropZone;
}

export interface CanvasHandlers {
    onToggleCollapse: (nodeId: number) => void;
    onRename: (nodeId: number, title: string) => void;
    onCancelRename: () => void;
    onOpenSectionMenu: (nodeId: number, anchor: { x: number; y: number }) => void;
    onOpenTaskMenu: (taskId: number, anchor: { x: number; y: number }) => void;
    onOpenTask: (taskId: number) => void;
    onAssignTask: (taskId: number, wbsNodeId: number | null) => void;
    onMoveSection: (nodeId: number, parentId: number | null, beforeId: number | null) => void;
    onAddRootSection: () => void;
}

interface StructureCanvasProps {
    project: Project;
    nodes: WbsNode[];
    tasks: TaskCompact[];
    stages: ProjectStage[];
    collapsed: Set<number>;
    layoutMode: WbsLayoutMode;
    editingNodeId: number | null;
    selectedTaskId: number | null;
    /** Задача, которую сейчас тащат из пула. */
    draggingTask: TaskCompact | null;
    handlers: CanvasHandlers;
}

export function StructureCanvas(props: StructureCanvasProps) {
    return (
        <ReactFlowProvider>
            <CanvasInner {...props} />
        </ReactFlowProvider>
    );
}

function CanvasInner({
    project,
    nodes,
    tasks,
    stages,
    collapsed,
    layoutMode,
    editingNodeId,
    selectedTaskId,
    draggingTask,
    handlers,
}: StructureCanvasProps) {
    const { fitView, setCenter, getZoom, screenToFlowPosition } = useReactFlow();
    const [flowNodes, setFlowNodes] = useState<Node[]>([]);
    const [flowEdges, setFlowEdges] = useState<Edge[]>([]);
    const [zoom, setZoom] = useState(1);
    const [dropTargetId, setDropTargetId] = useState<number | null>(null);
    const [sectionDrop, setSectionDrop] = useState<SectionDropState | null>(null);
    const [search, setSearch] = useState("");
    const [isSearchOpen, setSearchOpen] = useState(false);
    const layoutRequestRef = useRef(0);
    const layoutModeRef = useRef(layoutMode);

    const stagesById = useMemo(() => new Map(stages.map((stage) => [stage.id, stage])), [stages]);
    const isOverdue = useCallback(
        (task: TaskCompact) => dueTone(task.due_date, task.is_done) === "danger",
        [],
    );
    const tree = useMemo(() => buildWbsTree(nodes, tasks, isOverdue), [nodes, tasks, isOverdue]);

    const detail: "full" | "compact" | "minimal" =
        zoom >= DETAIL_FULL_ZOOM ? "full" : zoom >= DETAIL_COMPACT_ZOOM ? "compact" : "minimal";
    const showTasks = detail !== "minimal";

    const graph = useMemo(
        () => buildWbsGraph({ roots: tree.roots, collapsed, showTasks }),
        [tree.roots, collapsed, showTasks],
    );

    /**
     * Раскладка пересчитывается только при смене топологии графа или режима —
     * hover, выделение и открытие панели задачи её не трогают (§43 ТЗ).
     */
    const topologyKey = useMemo(
        () => `${layoutMode}|${graph.nodes.map((node) => node.id).join(",")}`,
        [graph.nodes, layoutMode],
    );

    useEffect(() => {
        const requestId = ++layoutRequestRef.current;
        let cancelled = false;

        layoutWbsGraph(graph, layoutMode)
            .then(({ positions }) => {
                if (cancelled || requestId !== layoutRequestRef.current) {
                    return;
                }
                setFlowNodes(
                    graph.nodes.map((node) => ({
                        id: node.id,
                        type: node.kind,
                        position: positions.get(node.id) ?? { x: 0, y: 0 },
                        width: node.width,
                        height: node.height,
                        draggable: node.kind === "section",
                        selectable: node.kind !== "project",
                        data: {},
                    })),
                );
                setFlowEdges(
                    graph.edges.map((edge) => ({
                        id: edge.id,
                        source: edge.source,
                        target: edge.target,
                        type: "smoothstep",
                    })),
                );
                // Смена режима полностью меняет геометрию — возвращаем граф в кадр.
                if (layoutModeRef.current !== layoutMode) {
                    layoutModeRef.current = layoutMode;
                    window.setTimeout(() => fitView({ duration: 240, padding: 0.15 }), 60);
                }
            })
            .catch(() => undefined);

        return () => {
            cancelled = true;
        };
        // graph пересобирается вместе с topologyKey, поэтому его достаточно.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [topologyKey]);

    /**
     * Данные узлов обновляются отдельно от раскладки: изменение прогресса или
     * выделения не должно перезапускать layout.
     *
     * Узлы, которых уже нет в данных, отбрасываются: между удалением раздела и
     * пересчётом раскладки они ещё живут в `flowNodes`, и отрисовать их нечем.
     */
    const decoratedNodes = useMemo<Node[]>(
        () =>
            flowNodes.flatMap((node): Node[] => {
                const parsed = parseGraphNodeId(node.id);
                if (parsed?.kind === "project") {
                    return [{ ...node, data: { project, progress: tree.total } }];
                }
                if (parsed?.kind === "section") {
                    const section = tree.byId.get(parsed.nodeId);
                    if (section === undefined) {
                        return [];
                    }
                    const graphNode = graph.nodes.find((item) => item.id === node.id);
                    const isSectionTarget = sectionDrop?.targetId === parsed.nodeId;
                    return [{
                        ...node,
                        data: {
                            section,
                            isCollapsed: collapsed.has(parsed.nodeId),
                            hiddenSections: graphNode?.hiddenSections ?? 0,
                            hiddenTasks: graphNode?.hiddenTasks ?? 0,
                            isDropTarget:
                                dropTargetId === parsed.nodeId ||
                                (isSectionTarget && sectionDrop?.zone === "inside"),
                            dropZone: isSectionTarget ? sectionDrop.zone : null,
                            isEditing: editingNodeId === parsed.nodeId,
                            detail,
                            onToggleCollapse: handlers.onToggleCollapse,
                            onRename: handlers.onRename,
                            onCancelRename: handlers.onCancelRename,
                            onOpenMenu: handlers.onOpenSectionMenu,
                        },
                    }];
                }
                if (parsed?.kind === "task") {
                    const task = tasks.find((item) => item.id === parsed.taskId);
                    if (task === undefined) {
                        return [];
                    }
                    return [{
                        ...node,
                        selected: task.id === selectedTaskId,
                        data: {
                            task,
                            stage: stagesById.get(task.stage_id),
                            detail,
                            onOpen: handlers.onOpenTask,
                            onContextMenu: handlers.onOpenTaskMenu,
                        },
                    }];
                }
                return [];
            }),
        [
            flowNodes,
            graph.nodes,
            tree,
            project,
            tasks,
            stagesById,
            collapsed,
            dropTargetId,
            sectionDrop,
            editingNodeId,
            selectedTaskId,
            detail,
            handlers,
        ],
    );

    const selectedPathEdgeIds = useMemo(() => {
        const ids = new Set<string>();
        if (selectedTaskId === null) return ids;
        let target = taskNodeId(selectedTaskId);
        for (;;) {
            const parentEdge = flowEdges.find((edge) => edge.target === target);
            if (!parentEdge) break;
            ids.add(parentEdge.id);
            target = parentEdge.source;
        }
        return ids;
    }, [flowEdges, selectedTaskId]);

    /** Ребро без обоих концов React Flow отрисовать не может. */
    const visibleEdges = useMemo(() => {
        const present = new Set(decoratedNodes.map((node) => node.id));
        return flowEdges
            .filter((edge) => present.has(edge.source) && present.has(edge.target))
            .map((edge) => ({
                ...edge,
                style: selectedPathEdgeIds.has(edge.id)
                    ? { stroke: "var(--color-accent)", strokeWidth: 1.5, opacity: 0.78 }
                    : { stroke: "var(--color-border-strong)", strokeWidth: 1, opacity: 0.52 },
            }));
    }, [decoratedNodes, flowEdges, selectedPathEdgeIds]);

    /**
     * Раздел под курсором — единственная валидная цель сброса (§26 ТЗ).
     * Верхняя и нижняя четверть узла означают вставку рядом, середина — внутрь.
     */
    const findSectionAt = useCallback(
        (
            clientX: number,
            clientY: number,
            excludeIds?: Set<number>,
        ): { section: WbsTreeNode; zone: SectionDropZone } | null => {
            const point = screenToFlowPosition({ x: clientX, y: clientY });
            for (const node of flowNodes) {
                const parsed = parseGraphNodeId(node.id);
                if (parsed?.kind !== "section" || excludeIds?.has(parsed.nodeId)) {
                    continue;
                }
                const width = node.width ?? 0;
                const height = node.height ?? 0;
                const inside =
                    point.x >= node.position.x &&
                    point.x <= node.position.x + width &&
                    point.y >= node.position.y &&
                    point.y <= node.position.y + height;
                if (!inside) {
                    continue;
                }
                const section = tree.byId.get(parsed.nodeId);
                if (section === undefined) {
                    return null;
                }
                const offset = (point.y - node.position.y) / Math.max(height, 1);
                const zone: SectionDropZone =
                    offset < 0.25 ? "before" : offset > 0.75 ? "after" : "inside";
                return { section, zone };
            }
            return null;
        },
        [flowNodes, screenToFlowPosition, tree.byId],
    );

    const handleDragOver = useCallback(
        (event: React.DragEvent) => {
            if (!event.dataTransfer.types.includes(TASK_DRAG_TYPE)) {
                return;
            }
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            const hit = findSectionAt(event.clientX, event.clientY);
            setDropTargetId(hit?.section.node.id ?? null);
        },
        [findSectionAt],
    );

    const handleDrop = useCallback(
        (event: React.DragEvent) => {
            event.preventDefault();
            setDropTargetId(null);
            // Идентификатор берём из dataTransfer: состояние React к моменту
            // drop может быть ещё не обновлено после dragstart.
            const taskId = Number(event.dataTransfer.getData(TASK_DRAG_TYPE));
            const hit = findSectionAt(event.clientX, event.clientY);
            if (!Number.isFinite(taskId) || taskId === 0 || hit === null) {
                return;
            }
            handlers.onAssignTask(taskId, hit.section.node.id);
        },
        [findSectionAt, handlers],
    );

    const handleNodeDrag: OnNodeDrag = useCallback(
        (event, node) => {
            const parsed = parseGraphNodeId(node.id);
            if (parsed?.kind !== "section") {
                return;
            }
            // Перенос внутрь собственного потомка создал бы цикл — такие цели исключаем.
            const forbidden = collectSubtreeIds(nodes, parsed.nodeId);
            const pointer = pointerPosition(event);
            const hit =
                pointer === null ? null : findSectionAt(pointer.x, pointer.y, forbidden);
            setSectionDrop(
                hit === null
                    ? null
                    : { movedId: parsed.nodeId, targetId: hit.section.node.id, zone: hit.zone },
            );
        },
        [nodes, findSectionAt],
    );

    const handleNodeDragStop: OnNodeDrag = useCallback(
        (_event, node) => {
            const pending = sectionDrop;
            setSectionDrop(null);
            const parsed = parseGraphNodeId(node.id);
            if (parsed?.kind !== "section" || pending === null) {
                // Без валидной цели узел вернётся на место следующей раскладкой.
                setFlowNodes((current) => [...current]);
                return;
            }
            const target = resolveSectionDrop(
                nodes,
                pending.targetId,
                pending.zone,
                pending.movedId,
            );
            if (target === null) {
                setFlowNodes((current) => [...current]);
                return;
            }
            handlers.onMoveSection(pending.movedId, target.parentId, target.beforeId);
        },
        [nodes, sectionDrop, handlers],
    );

    const handleNodeClick: NodeMouseHandler = useCallback(
        (_event, node) => {
            const parsed = parseGraphNodeId(node.id);
            if (parsed?.kind === "task") {
                handlers.onOpenTask(parsed.taskId);
            }
        },
        [handlers],
    );

    /** Поиск раскрывает предков найденного элемента и центрирует его (§36 ТЗ). */
    const searchResults = useMemo(() => {
        const query = search.trim().toLowerCase();
        if (query === "") {
            return [];
        }
        const sections = flattenTree(tree.roots)
            .filter(
                (item) =>
                    item.node.title.toLowerCase().includes(query) || item.number.startsWith(query),
            )
            .map((item) => ({
                id: sectionNodeId(item.node.id),
                label: `${item.number} ${item.node.title}`,
                nodeId: item.node.id,
                kind: "section" as const,
            }));
        const matchedTasks = tasks
            .filter(
                (task) =>
                    task.wbs_node_id !== null &&
                    (task.title.toLowerCase().includes(query) ||
                        task.key.toLowerCase().includes(query)),
            )
            .map((task) => ({
                id: taskNodeId(task.id),
                label: `${task.key} ${task.title}`,
                nodeId: task.wbs_node_id as number,
                kind: "task" as const,
            }));
        return [...sections, ...matchedTasks].slice(0, 8);
    }, [search, tree.roots, tasks]);

    const focusResult = useCallback(
        (result: { id: string; nodeId: number; kind: "section" | "task" }) => {
            const toExpand =
                result.kind === "section"
                    ? collectAncestorIds(nodes, result.nodeId)
                    : [result.nodeId, ...collectAncestorIds(nodes, result.nodeId)];
            for (const id of toExpand) {
                if (collapsed.has(id)) {
                    handlers.onToggleCollapse(id);
                }
            }
            window.setTimeout(() => {
                const target = flowNodes.find((node) => node.id === result.id);
                if (target) {
                    setCenter(
                        target.position.x + (target.width ?? 0) / 2,
                        target.position.y + (target.height ?? 0) / 2,
                        { zoom: Math.max(getZoom(), 0.9), duration: 240 },
                    );
                }
            }, FOCUS_DELAY_MS);
            setSearch("");
            setSearchOpen(false);
        },
        [nodes, collapsed, handlers, flowNodes, setCenter, getZoom],
    );

    if (tree.roots.length === 0) {
        return (
            <div className="flex h-full items-center justify-center p-6">
                <EmptyState
                    title="Структура"
                    description={
                        "Организуйте задачи проекта в ИСР: создайте основные разделы, " +
                        "а затем распределите по ним существующие задачи."
                    }
                    icon={<Network size={24} />}
                    action={
                        <Button
                            variant="primary"
                            icon={<Plus size={15} />}
                            onClick={handlers.onAddRootSection}
                        >
                            Создать раздел
                        </Button>
                    }
                />
            </div>
        );
    }

    return (
        <div
            className="material-mineral relative h-full w-full"
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onDragLeave={() => setDropTargetId(null)}
        >
            <ReactFlow
                nodes={decoratedNodes}
                edges={visibleEdges}
                nodeTypes={NODE_TYPES}
                onNodeClick={handleNodeClick}
                onNodeDrag={handleNodeDrag}
                onNodeDragStop={handleNodeDragStop}
                onMove={(_event, viewport) => setZoom(viewport.zoom)}
                nodesConnectable={false}
                edgesFocusable={false}
                minZoom={0.25}
                maxZoom={1.8}
                fitView
                proOptions={{ hideAttribution: true }}
                className="bg-transparent"
            >
                <Background
                    variant={BackgroundVariant.Dots}
                    gap={22}
                    size={1}
                    color="var(--color-border-subtle)"
                />
                <Controls
                    showInteractive={false}
                    className="!overflow-hidden !rounded-[var(--radius-control)] !border-line-subtle !bg-floating !shadow-panel [&_button]:!border-line-subtle [&_button]:!bg-floating [&_button]:!fill-secondary hover:[&_button]:!bg-hover"
                />
                <MiniMap
                    pannable
                    zoomable
                    ariaLabel="Обзорная карта структуры"
                    className="!rounded-[var(--radius-control)] !border !border-line-subtle !bg-floating !shadow-panel"
                    maskColor="var(--surface-void)"
                    nodeColor={(node) =>
                        node.type === "project"
                            ? project.color
                            : node.type === "section"
                              ? "var(--color-accent)"
                              : "var(--surface-pressed)"
                    }
                />
            </ReactFlow>

            <div className="pointer-events-none absolute top-3 right-3 left-3 flex justify-between gap-2">
                <div className="pointer-events-auto flex flex-col gap-1.5">
                    {isSearchOpen ? (
                        <div className="glass w-72 rounded-md p-1.5 shadow-panel">
                            <Input
                                autoFocus
                                value={search}
                                aria-label="Поиск по структуре"
                                placeholder="Раздел или задача"
                                onChange={(event) => setSearch(event.target.value)}
                                onKeyDown={(event) => {
                                    if (event.key === "Escape") {
                                        setSearch("");
                                        setSearchOpen(false);
                                    }
                                    if (event.key === "Enter" && searchResults.length > 0) {
                                        focusResult(searchResults[0]);
                                    }
                                }}
                            />
                            {searchResults.length > 0 && (
                                <ul className="mt-1 flex flex-col">
                                    {searchResults.map((result) => (
                                        <li key={result.id}>
                                            <button
                                                type="button"
                                                onClick={() => focusResult(result)}
                                                className="w-full truncate rounded-sm px-2 py-1 text-left text-[12px] text-secondary hover:bg-hover hover:text-primary"
                                            >
                                                {result.label}
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    ) : (
                        <Button
                            size="sm"
                            icon={<Search size={13} />}
                            className="glass"
                            onClick={() => setSearchOpen(true)}
                        >
                            Поиск
                        </Button>
                    )}
                </div>

                <div className="pointer-events-auto flex items-center gap-1.5">
                    <span
                        className={cn(
                            "glass rounded-md px-2 py-1 font-mono text-[11px] text-muted",
                            detail === "minimal" && "text-warning",
                        )}
                        title={
                            detail === "minimal"
                                ? "Задачи скрыты: показана архитектура проекта"
                                : "Масштаб"
                        }
                    >
                        {Math.round(zoom * 100)}%
                    </span>
                    <Button
                        size="sm"
                        className="glass"
                        icon={<Maximize2 size={13} />}
                        onClick={() => fitView({ duration: 240, padding: 0.15 })}
                    >
                        Вся структура
                    </Button>
                </div>
            </div>

            {sectionDrop !== null && (
                <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2">
                    <p className="glass rounded-md px-3 py-1.5 text-[12px] text-secondary shadow-panel">
                        {sectionDrop.zone === "inside" && "Сделать подразделом: "}
                        {sectionDrop.zone === "before" && "Поставить перед: "}
                        {sectionDrop.zone === "after" && "Поставить после: "}
                        {tree.byId.get(sectionDrop.targetId)?.node.title ?? ""}
                    </p>
                </div>
            )}

            {draggingTask !== null && sectionDrop === null && (
                <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2">
                    <p className="glass rounded-md px-3 py-1.5 text-[12px] text-secondary shadow-panel">
                        {dropTargetId === null
                            ? `Перетащите ${draggingTask.key} на раздел`
                            : `Поместить в: ${tree.byId.get(dropTargetId)?.node.title ?? ""}`}
                    </p>
                </div>
            )}
        </div>
    );
}
