import type { KanbanStage, WbsNode } from "@/lib/types";

export const WBS_MAP_NODE_WIDTH = 232;
export const WBS_MAP_NODE_HEIGHT = 104;

const HORIZONTAL_GAP = 32;
const VERTICAL_GAP = 84;
const MAP_PADDING = 72;
const PROJECT_ROOT_WIDTH = 280;

export interface WbsStageCount {
    stageId: number;
    count: number;
}

export interface WbsMapNodeSummary {
    taskCount: number;
    doneCount: number;
    overdueCount: number;
    stageCounts: WbsStageCount[];
}

export interface WbsMapLayoutNode extends WbsMapNodeSummary {
    key: string;
    sourceId: number | null;
    parentKey: string | null;
    code: string;
    title: string;
    role: WbsNode["role"];
    task: WbsNode["task"];
    depth: number;
    x: number;
    y: number;
    width: number;
    height: number;
    hasChildren: boolean;
    isExpanded: boolean;
    hiddenNodeCount: number;
    directSearchMatch: boolean;
    containsSearchMatch: boolean;
}

export interface WbsMapLayoutEdge {
    key: string;
    sourceKey: string;
    targetKey: string;
    sourceX: number;
    sourceY: number;
    targetX: number;
    targetY: number;
}

export interface WbsMapSearchResult {
    nodeId: number;
    code: string;
    title: string;
    taskId: number | null;
}

export interface WbsMapModel {
    nodes: WbsMapLayoutNode[];
    edges: WbsMapLayoutEdge[];
    width: number;
    height: number;
    totalNodeCount: number;
    visibleNodeCount: number;
    searchResults: WbsMapSearchResult[];
    summary: WbsMapNodeSummary;
}

interface AnnotatedNode {
    source: WbsNode;
    children: AnnotatedNode[];
    summary: WbsMapNodeSummary;
    descendantCount: number;
    directSearchMatch: boolean;
    containsSearchMatch: boolean;
}

interface VisibleNode {
    annotated: AnnotatedNode | null;
    key: string;
    parentKey: string | null;
    depth: number;
    children: VisibleNode[];
    x: number;
}

export interface BuildWbsMapOptions {
    expandedNodeIds: ReadonlySet<number>;
    activeRootId: number | null;
    search: string;
    now?: Date;
}

function mergeStageCounts(target: Map<number, number>, counts: WbsStageCount[]): void {
    counts.forEach(({ stageId, count }) => {
        target.set(stageId, (target.get(stageId) ?? 0) + count);
    });
}

function stageCountsFromMap(counts: Map<number, number>): WbsStageCount[] {
    return Array.from(counts, ([stageId, count]) => ({ stageId, count }));
}

function isTaskOverdue(node: WbsNode, doneStageIds: ReadonlySet<number>, today: string): boolean {
    return Boolean(
        node.task?.due_date
        && node.task.due_date < today
        && !doneStageIds.has(node.task.stage_id),
    );
}

function matchesSearch(node: WbsNode, normalizedSearch: string): boolean {
    if (!normalizedSearch) return false;
    return [node.code, node.phase_name, node.title, node.role, node.task?.stage_name]
        .some((value) => value?.toLocaleLowerCase("ru-RU").includes(normalizedSearch));
}

function localDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function annotateNode(
    node: WbsNode,
    doneStageIds: ReadonlySet<number>,
    normalizedSearch: string,
    today: string,
    searchResults: WbsMapSearchResult[],
): AnnotatedNode {
    const children = node.children.map((child) => annotateNode(
        child,
        doneStageIds,
        normalizedSearch,
        today,
        searchResults,
    ));
    const directSearchMatch = matchesSearch(node, normalizedSearch);
    if (directSearchMatch) {
        searchResults.push({
            nodeId: node.id,
            code: node.code,
            title: node.phase_name ?? node.title,
            taskId: node.task?.id ?? null,
        });
    }

    if (node.task) {
        return {
            source: node,
            children,
            descendantCount: children.reduce((sum, child) => sum + child.descendantCount + 1, 0),
            directSearchMatch,
            containsSearchMatch: directSearchMatch || children.some((child) => child.containsSearchMatch),
            summary: {
                taskCount: 1,
                doneCount: doneStageIds.has(node.task.stage_id) ? 1 : 0,
                overdueCount: isTaskOverdue(node, doneStageIds, today) ? 1 : 0,
                stageCounts: [{ stageId: node.task.stage_id, count: 1 }],
            },
        };
    }

    const stageCounts = new Map<number, number>();
    children.forEach((child) => mergeStageCounts(stageCounts, child.summary.stageCounts));
    return {
        source: node,
        children,
        descendantCount: children.reduce((sum, child) => sum + child.descendantCount + 1, 0),
        directSearchMatch,
        containsSearchMatch: directSearchMatch || children.some((child) => child.containsSearchMatch),
        summary: {
            taskCount: children.reduce((sum, child) => sum + child.summary.taskCount, 0),
            doneCount: children.reduce((sum, child) => sum + child.summary.doneCount, 0),
            overdueCount: children.reduce((sum, child) => sum + child.summary.overdueCount, 0),
            stageCounts: stageCountsFromMap(stageCounts),
        },
    };
}

function buildProjectSummary(roots: AnnotatedNode[]): WbsMapNodeSummary {
    const stageCounts = new Map<number, number>();
    roots.forEach((root) => mergeStageCounts(stageCounts, root.summary.stageCounts));
    return {
        taskCount: roots.reduce((sum, root) => sum + root.summary.taskCount, 0),
        doneCount: roots.reduce((sum, root) => sum + root.summary.doneCount, 0),
        overdueCount: roots.reduce((sum, root) => sum + root.summary.overdueCount, 0),
        stageCounts: stageCountsFromMap(stageCounts),
    };
}

function collectSourceIds(roots: AnnotatedNode[]): Set<number> {
    const ids = new Set<number>();
    function visit(node: AnnotatedNode) {
        ids.add(node.source.id);
        node.children.forEach(visit);
    }
    roots.forEach(visit);
    return ids;
}

function buildVisibleNode(
    annotated: AnnotatedNode,
    parentKey: string,
    depth: number,
    expandedNodeIds: ReadonlySet<number>,
    forceSearchPathsOpen: boolean,
): VisibleNode {
    const isExpanded = expandedNodeIds.has(annotated.source.id)
        || (forceSearchPathsOpen && annotated.containsSearchMatch);
    return {
        annotated,
        key: `wbs-${annotated.source.id}`,
        parentKey,
        depth,
        x: 0,
        children: isExpanded
            ? annotated.children.map((child) => buildVisibleNode(
                child,
                `wbs-${annotated.source.id}`,
                depth + 1,
                expandedNodeIds,
                forceSearchPathsOpen,
            ))
            : [],
    };
}

function assignHorizontalPositions(root: VisibleNode): void {
    let nextLeafX = MAP_PADDING;

    function visit(node: VisibleNode): void {
        if (node.children.length === 0) {
            node.x = nextLeafX;
            nextLeafX += WBS_MAP_NODE_WIDTH + HORIZONTAL_GAP;
            return;
        }
        node.children.forEach(visit);
        const first = node.children[0];
        const last = node.children[node.children.length - 1];
        const childrenCenter = (first.x + last.x + WBS_MAP_NODE_WIDTH) / 2;
        const ownWidth = node.annotated ? WBS_MAP_NODE_WIDTH : PROJECT_ROOT_WIDTH;
        node.x = childrenCenter - ownWidth / 2;
    }

    visit(root);
}

function flattenVisibleTree(
    root: VisibleNode,
    projectSummary: WbsMapNodeSummary,
): { nodes: WbsMapLayoutNode[]; edges: WbsMapLayoutEdge[] } {
    const nodes: WbsMapLayoutNode[] = [];
    const edges: WbsMapLayoutEdge[] = [];

    function visit(node: VisibleNode): void {
        const annotated = node.annotated;
        const width = annotated ? WBS_MAP_NODE_WIDTH : PROJECT_ROOT_WIDTH;
        const y = MAP_PADDING + node.depth * (WBS_MAP_NODE_HEIGHT + VERTICAL_GAP);
        const source = annotated?.source;
        nodes.push({
            key: node.key,
            sourceId: source?.id ?? null,
            parentKey: node.parentKey,
            code: source?.code ?? "VERA",
            title: source ? source.phase_name ?? source.title : "Карта проекта «Вера»",
            role: source?.role ?? null,
            task: source?.task ?? null,
            depth: node.depth,
            x: node.x,
            y,
            width,
            height: WBS_MAP_NODE_HEIGHT,
            hasChildren: Boolean(annotated?.children.length),
            isExpanded: Boolean(annotated && node.children.length > 0),
            hiddenNodeCount: annotated && node.children.length === 0 ? annotated.descendantCount : 0,
            directSearchMatch: annotated?.directSearchMatch ?? false,
            containsSearchMatch: annotated?.containsSearchMatch ?? false,
            ...(annotated?.summary ?? projectSummary),
        });

        node.children.forEach((child) => {
            const childWidth = child.annotated ? WBS_MAP_NODE_WIDTH : PROJECT_ROOT_WIDTH;
            edges.push({
                key: `${node.key}-${child.key}`,
                sourceKey: node.key,
                targetKey: child.key,
                sourceX: node.x + width / 2,
                sourceY: y + WBS_MAP_NODE_HEIGHT,
                targetX: child.x + childWidth / 2,
                targetY: MAP_PADDING + child.depth * (WBS_MAP_NODE_HEIGHT + VERTICAL_GAP),
            });
            visit(child);
        });
    }

    visit(root);
    return { nodes, edges };
}

export function buildWbsMapModel(
    tree: WbsNode[],
    stages: KanbanStage[],
    options: BuildWbsMapOptions,
): WbsMapModel {
    const doneStageIds = new Set(stages.filter((stage) => stage.is_done_stage).map((stage) => stage.id));
    const normalizedSearch = options.search.trim().toLocaleLowerCase("ru-RU");
    const today = localDateKey(options.now ?? new Date());
    const searchResults: WbsMapSearchResult[] = [];
    const allRoots = tree.map((node) => annotateNode(
        node,
        doneStageIds,
        normalizedSearch,
        today,
        searchResults,
    ));
    const roots = options.activeRootId === null
        ? allRoots
        : allRoots.filter((root) => root.source.id === options.activeRootId);
    const activeSourceIds = collectSourceIds(roots);
    const summary = buildProjectSummary(roots);
    const visibleRoot: VisibleNode = {
        annotated: null,
        key: "project-root",
        parentKey: null,
        depth: 0,
        x: 0,
        children: roots.map((root) => buildVisibleNode(
            root,
            "project-root",
            1,
            options.expandedNodeIds,
            Boolean(normalizedSearch),
        )),
    };
    assignHorizontalPositions(visibleRoot);
    const { nodes, edges } = flattenVisibleTree(visibleRoot, summary);
    const maxX = nodes.reduce((maximum, node) => Math.max(maximum, node.x + node.width), 0);
    const maxY = nodes.reduce((maximum, node) => Math.max(maximum, node.y + node.height), 0);

    return {
        nodes,
        edges,
        width: Math.max(maxX + MAP_PADDING, 640),
        height: Math.max(maxY + MAP_PADDING, 420),
        totalNodeCount: roots.reduce((sum, root) => sum + root.descendantCount + 1, 0),
        visibleNodeCount: Math.max(nodes.length - 1, 0),
        searchResults: searchResults.filter((result) => activeSourceIds.has(result.nodeId)),
        summary,
    };
}

export function stageCount(summary: WbsMapNodeSummary, stageId: number): number {
    return summary.stageCounts.find((entry) => entry.stageId === stageId)?.count ?? 0;
}
