import { useCallback, useMemo, useRef, useState } from "react";
import {
    applyNodeChanges,
    Background,
    BackgroundVariant,
    Controls,
    ReactFlow,
    ReactFlowProvider,
    useReactFlow,
    type NodeChange,
    type OnNodeDrag,
    type Viewport,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Move, Plus, StickyNote } from "lucide-react";
import { ApiError } from "@/lib/api";
import {
    findAvailableStickerPosition,
    normalizeStickerPosition,
    STICKER_NODE_HEIGHT,
    STICKER_NODE_WIDTH,
    type ProjectSticker,
    type ProjectStickerCreateInput,
    type ProjectStickerInput,
    type ProjectStickerPositionInput,
} from "@/lib/board/stickers";
import type { Project, ProjectMember, Task } from "@/lib/types";
import { useUiStore } from "@/stores/ui";
import {
    ProjectStickerNode,
    type ProjectStickerCanvasNode,
    type ProjectStickerNodeData,
} from "@/components/board/ProjectStickerCard";
import { ProjectStickerDialog } from "@/components/board/ProjectStickerDialog";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorMessage } from "@/components/ui/States";

const NODE_TYPES = { sticker: ProjectStickerNode };

type EditorState = { mode: "create" } | { mode: "edit"; sticker: ProjectSticker } | null;

interface ProjectStickerBoardProps {
    project: Project;
    stickers: ProjectSticker[];
    members: ProjectMember[];
    tasks: Task[];
    tasksLoading: boolean;
    tasksError: Error | null;
    isSaving: boolean;
    isDeleting: boolean;
    onRetryTasks: () => void;
    onCreate: (input: ProjectStickerCreateInput) => Promise<ProjectSticker>;
    onUpdate: (sticker: ProjectSticker, input: ProjectStickerInput) => Promise<unknown>;
    onMove: (
        sticker: ProjectSticker,
        position: ProjectStickerPositionInput,
    ) => Promise<ProjectSticker>;
    onResize: (sticker: ProjectSticker, size: { width: number; height: number }) => Promise<ProjectSticker>;
    onDelete: (sticker: ProjectSticker) => Promise<unknown>;
}

interface StickerNodeOverride {
    node: ProjectStickerCanvasNode;
    sourceX: number;
    sourceY: number;
    sourceWidth?: number;
    sourceHeight?: number;
}

function mutationMessage(error: unknown, fallback: string): string {
    if (error instanceof ApiError && error.status === 409) {
        return "Стикер уже изменён другим участником. Доска обновлена — повторите действие.";
    }
    return error instanceof Error && error.message ? error.message : fallback;
}

function persistedPosition(sticker: ProjectSticker) {
    return { x: sticker.canvas_x, y: sticker.canvas_y };
}

function createCanvasNode(
    sticker: ProjectSticker,
    data: ProjectStickerNodeData,
    isMoving = false,
): ProjectStickerCanvasNode {
    return {
        id: String(sticker.id),
        type: "sticker",
        position: persistedPosition(sticker),
        width: sticker.width ?? STICKER_NODE_WIDTH,
        height: sticker.height ?? STICKER_NODE_HEIGHT,
        draggable: !isMoving,
        deletable: false,
        connectable: false,
        selectable: true,
        ariaLabel: `Стикер: ${sticker.body.slice(0, 80)}`,
        data,
    };
}

export function ProjectStickerBoard(props: ProjectStickerBoardProps) {
    return (
        <ReactFlowProvider>
            <ProjectStickerBoardInner {...props} />
        </ReactFlowProvider>
    );
}

function ProjectStickerBoardInner({
    project,
    stickers,
    members,
    tasks,
    tasksLoading,
    tasksError,
    isSaving,
    isDeleting,
    onRetryTasks,
    onCreate,
    onUpdate,
    onMove,
    onResize,
    onDelete,
}: ProjectStickerBoardProps) {
    const { getZoom, screenToFlowPosition, setCenter } = useReactFlow();
    const viewportKey = `project-sticker-board-viewport:${project.id}`;
    const [savedViewport] = useState<Viewport | null>(() => {
        try {
            const value = window.localStorage.getItem(viewportKey);
            if (!value) return null;
            const parsed = JSON.parse(value) as Partial<Viewport>;
            return typeof parsed.x === "number" && Number.isFinite(parsed.x)
                && typeof parsed.y === "number" && Number.isFinite(parsed.y)
                && typeof parsed.zoom === "number" && Number.isFinite(parsed.zoom) && parsed.zoom > 0
                ? { x: parsed.x as number, y: parsed.y as number, zoom: parsed.zoom as number }
                : null;
        } catch { return null; }
    });
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);
    const canvasRef = useRef<HTMLDivElement>(null);
    const [editor, setEditor] = useState<EditorState>(null);
    const [createPosition, setCreatePosition] = useState<ProjectStickerPositionInput | null>(null);
    const [editorError, setEditorError] = useState<string | null>(null);
    const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const [positionError, setPositionError] = useState<string | null>(null);
    const [movingStickerIds, setMovingStickerIds] = useState<Set<number>>(() => new Set());
    const tasksById = useMemo(
        () => new Map(tasks.map((task) => [task.id, task])),
        [tasks],
    );

    const editSticker = useCallback((sticker: ProjectSticker) => {
        setCreatePosition(null);
        setEditorError(null);
        setEditor({ mode: "edit", sticker });
    }, []);
    const requestDelete = useCallback((sticker: ProjectSticker) => {
        setDeleteError(null);
        setDeleteTargetId(sticker.id);
    }, []);
    const nodeData = useCallback(
        (sticker: ProjectSticker): ProjectStickerNodeData => ({
            projectId: project.id,
            sticker,
            members,
            tasksById,
            onOpenTask: setSelectedTaskId,
            onEdit: editSticker,
            onDelete: requestDelete,
            onResize: (item, width, height) => {
                void onResize(item, { width, height }).catch((error) => {
                    setPositionError(mutationMessage(error, "Не удалось сохранить размер стикера."));
                });
            },
        }),
        [editSticker, members, onResize, project.id, requestDelete, setSelectedTaskId, tasksById],
    );
    const [nodeOverrides, setNodeOverrides] = useState<Map<string, StickerNodeOverride>>(
        () => new Map(),
    );
    const flowNodes = useMemo(
        () => stickers.map((sticker) => {
            const next = createCanvasNode(
                sticker,
                nodeData(sticker),
                movingStickerIds.has(sticker.id),
            );
            const override = nodeOverrides.get(next.id);
            if (override === undefined
                || override.sourceX !== sticker.canvas_x
                || override.sourceY !== sticker.canvas_y
                || override.sourceWidth !== (sticker.width ?? STICKER_NODE_WIDTH)
                || override.sourceHeight !== (sticker.height ?? STICKER_NODE_HEIGHT)) {
                return next;
            }
            return {
                ...next,
                position: override.node.position,
                selected: override.node.selected,
                measured: override.node.measured,
                width: override.node.width,
                height: override.node.height,
            };
        }),
        [movingStickerIds, nodeData, nodeOverrides, stickers],
    );

    const deleteTarget = deleteTargetId === null
        ? null
        : stickers.find((sticker) => sticker.id === deleteTargetId) ?? null;

    function openCreateDialog() {
        const rect = canvasRef.current?.getBoundingClientRect();
        const center = rect
            ? screenToFlowPosition({
                x: rect.left + rect.width / 2,
                y: rect.top + rect.height / 2,
            })
            : { x: 40 + STICKER_NODE_WIDTH / 2, y: 40 + STICKER_NODE_HEIGHT / 2 };
        setCreatePosition(findAvailableStickerPosition(stickers, {
            x: center.x - STICKER_NODE_WIDTH / 2,
            y: center.y - STICKER_NODE_HEIGHT / 2,
        }));
        setEditorError(null);
        setEditor({ mode: "create" });
    }

    async function saveSticker(input: ProjectStickerInput) {
        setEditorError(null);
        try {
            if (editor?.mode === "edit") {
                await onUpdate(editor.sticker, input);
                setEditor(null);
                return;
            }
            const position = findAvailableStickerPosition(
                stickers,
                createPosition ? { x: createPosition.canvas_x, y: createPosition.canvas_y } : { x: 40, y: 40 },
                { width: input.width, height: input.height },
            );
            const created = await onCreate({ ...input, ...position });
            setEditor(null);
            setCreatePosition(null);
            window.setTimeout(() => {
                void setCenter(
                    created.canvas_x + (created.width ?? STICKER_NODE_WIDTH) / 2,
                    created.canvas_y + (created.height ?? STICKER_NODE_HEIGHT) / 2,
                    { zoom: Math.max(getZoom(), 0.8), duration: 240 },
                );
            }, 60);
        } catch (error) {
            setEditorError(mutationMessage(error, "Не удалось сохранить стикер."));
        }
    }

    async function deleteSticker() {
        if (!deleteTarget) return;
        setDeleteError(null);
        try {
            await onDelete(deleteTarget);
            setDeleteTargetId(null);
        } catch (error) {
            setDeleteError(mutationMessage(error, "Не удалось удалить стикер."));
        }
    }

    const handleNodesChange = useCallback((changes: NodeChange<ProjectStickerCanvasNode>[]) => {
        const nextNodes = applyNodeChanges(changes, flowNodes);
        const stickersById = new Map(stickers.map((sticker) => [String(sticker.id), sticker]));
        setNodeOverrides(new Map(nextNodes.flatMap((node) => {
            const sticker = stickersById.get(node.id);
            return sticker === undefined
                ? []
                : [[node.id, {
                    node,
                    sourceX: sticker.canvas_x,
                    sourceY: sticker.canvas_y,
                    sourceWidth: sticker.width ?? STICKER_NODE_WIDTH,
                    sourceHeight: sticker.height ?? STICKER_NODE_HEIGHT,
                }] as const];
        })));
    }, [flowNodes, stickers]);

    const handleNodeDragStop: OnNodeDrag<ProjectStickerCanvasNode> = useCallback(
        (_event, node) => {
            const sticker = stickers.find((item) => item.id === Number(node.id));
            if (sticker === undefined || movingStickerIds.has(sticker.id)) return;
            const position = normalizeStickerPosition(node.position);
            if (position.canvas_x === sticker.canvas_x && position.canvas_y === sticker.canvas_y) {
                return;
            }

            setPositionError(null);
            setMovingStickerIds((current) => new Set(current).add(sticker.id));
            void onMove(sticker, position)
                .catch((error) => {
                    setNodeOverrides((current) => {
                        const next = new Map(current);
                        const override = next.get(node.id);
                        if (override !== undefined) {
                            next.set(node.id, {
                                ...override,
                                node: {
                                    ...override.node,
                                    position: persistedPosition(sticker),
                                },
                            });
                        }
                        return next;
                    });
                    setPositionError(mutationMessage(
                        error,
                        "Не удалось сохранить позицию стикера.",
                    ));
                })
                .finally(() => {
                    setMovingStickerIds((current) => {
                        const next = new Set(current);
                        next.delete(sticker.id);
                        return next;
                    });
                });
        },
        [movingStickerIds, onMove, stickers],
    );

    return (
        <div className="project-sticker-board">
            <header className="project-sticker-board__toolbar">
                <div>
                    <div className="flex items-center gap-2">
                        <StickyNote size={17} className="text-accent" aria-hidden="true" />
                        <h2 className="text-[15px] font-semibold text-primary">Стикеры проекта</h2>
                        <span className="font-mono text-[11px] text-muted">{stickers.length}</span>
                    </div>
                    <p className="mt-1 flex items-center gap-1.5 text-[12px] text-muted">
                        <Move size={12} aria-hidden="true" />
                        Перетаскивайте стикеры по холсту, меняйте размер за угол; свободная область — для навигации
                    </p>
                </div>
                <Button
                    variant="primary"
                    size="sm"
                    icon={<Plus size={14} aria-hidden="true" />}
                    onClick={openCreateDialog}
                >
                    Добавить стикер
                </Button>
            </header>

            {tasksError && (
                <ErrorMessage
                    title="Не удалось загрузить задачи"
                    message="Стикеры доступны, но названия связей временно не показаны."
                    action={
                        <Button size="sm" variant="ghost" onClick={onRetryTasks}>
                            Повторить
                        </Button>
                    }
                    className="mx-4 mt-3 sm:mx-5"
                />
            )}
            {positionError && (
                <ErrorMessage
                    title="Позиция не сохранена"
                    message={positionError}
                    className="mx-4 mt-3 sm:mx-5"
                />
            )}

            <section
                ref={canvasRef}
                className="project-sticker-canvas"
                aria-label="Холст стикеров проекта"
            >
                <ReactFlow
                    nodes={flowNodes}
                    edges={[]}
                    nodeTypes={NODE_TYPES}
                    onNodesChange={handleNodesChange}
                    onNodeDragStop={handleNodeDragStop}
                    nodesConnectable={false}
                    nodesFocusable={false}
                    deleteKeyCode={null}
                    minZoom={0.35}
                    maxZoom={1.5}
                    fitView={!savedViewport}
                    defaultViewport={savedViewport ?? undefined}
                    onMoveEnd={(_, viewport) => {
                        try {
                            window.localStorage.setItem(viewportKey, JSON.stringify(viewport));
                        } catch {
                            // Storage can be unavailable in private browsing; the board remains usable.
                        }
                    }}
                    fitViewOptions={{ padding: 0.16, maxZoom: 1 }}
                    zoomOnDoubleClick={false}
                    proOptions={{ hideAttribution: true }}
                    className="bg-transparent"
                >
                    <Background
                        variant={BackgroundVariant.Dots}
                        gap={20}
                        size={1}
                        color="var(--color-border-subtle)"
                    />
                    <Controls
                        showInteractive={false}
                        className="!overflow-hidden !rounded-[var(--radius-control)] !border-line-subtle !bg-floating !shadow-panel [&_button]:!border-line-subtle [&_button]:!bg-floating [&_button]:!fill-secondary hover:[&_button]:!bg-hover"
                    />
                </ReactFlow>

                {stickers.length === 0 && (
                    <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center p-4">
                        <EmptyState
                            icon={<StickyNote size={25} />}
                            title="На доске пока нет стикеров"
                            description="Зафиксируйте первое решение, вопрос или идею для команды проекта."
                            action={
                                <Button
                                    variant="primary"
                                    size="sm"
                                    icon={<Plus size={14} aria-hidden="true" />}
                                    onClick={openCreateDialog}
                                >
                                    Добавить стикер
                                </Button>
                            }
                            className="pointer-events-auto min-h-64 w-full max-w-md border border-line-subtle bg-surface/80 shadow-panel backdrop-blur-sm"
                        />
                    </div>
                )}
            </section>

            {editor && (
                <ProjectStickerDialog
                    key={editor.mode === "edit"
                        ? `${editor.sticker.id}:${editor.sticker.revision}`
                        : "new"}
                    projectId={project.id}
                    sticker={editor.mode === "edit" ? editor.sticker : null}
                    tasks={tasks}
                    tasksLoading={tasksLoading}
                    isSaving={isSaving}
                    error={editorError}
                    onClose={() => {
                        if (!isSaving) {
                            setEditor(null);
                            setCreatePosition(null);
                        }
                    }}
                    onSave={(input) => void saveSticker(input)}
                />
            )}

            {deleteTarget && (
                <Modal
                    isOpen
                    onOpenChange={(open) => {
                        if (!open && !isDeleting) setDeleteTargetId(null);
                    }}
                    isDismissable={!isDeleting}
                    title="Удалить стикер?"
                    description="Это действие нельзя отменить."
                    footer={
                        <>
                            <Button disabled={isDeleting} onClick={() => setDeleteTargetId(null)}>
                                Отмена
                            </Button>
                            <Button
                                variant="destructive"
                                disabled={isDeleting}
                                onClick={() => void deleteSticker()}
                            >
                                {isDeleting ? "Удаление…" : "Удалить"}
                            </Button>
                        </>
                    }
                >
                    <p className="line-clamp-4 whitespace-pre-wrap text-[13px] text-secondary">
                        {deleteTarget.body}
                    </p>
                    {deleteError && (
                        <p role="alert" className="mt-3 text-[12px] text-danger">{deleteError}</p>
                    )}
                </Modal>
            )}
        </div>
    );
}
