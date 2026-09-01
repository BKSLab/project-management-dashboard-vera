import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    ChevronsDownUp,
    ChevronsUpDown,
    CornerDownRight,
    ExternalLink,
    FolderPlus,
    Move,
    Pencil,
    Trash2,
    Unlink,
} from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { ProjectStage, WbsStructure } from "@/lib/types";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { useWbsMutations } from "@/lib/useWbsMutations";
import { buildWbsTree, flattenTree } from "@/lib/wbsTree";
import type { WbsLayoutMode } from "@/lib/wbsLayout";
import { useUiStore } from "@/stores/ui";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Field, Input } from "@/components/ui/Field";
import { ErrorMessage, Skeleton } from "@/components/ui/States";
import { CreateTaskDialog } from "@/components/tasks/CreateTaskDialog";
import { ContextMenu, type ContextMenuItem } from "@/components/wbs/ContextMenu";
import { MoveNodeDialog, MoveTaskDialog } from "@/components/wbs/MoveDialogs";
import { StructureCanvas, type CanvasHandlers } from "@/components/wbs/StructureCanvas";
import { TASK_DRAG_TYPE, TaskPool } from "@/components/wbs/TaskPool";
import type { TaskCompact } from "@/lib/types";

type MenuState =
    | { kind: "section"; nodeId: number; anchor: { x: number; y: number } }
    | { kind: "task"; taskId: number; anchor: { x: number; y: number } }
    | null;

export function StructurePage() {
    const project = useProjectOutlet();
    const collapsed = useUiStore((state) => state.collapsedWbsNodes);
    const toggleWbsNode = useUiStore((state) => state.toggleWbsNode);
    const expandWbsNodes = useUiStore((state) => state.expandWbsNodes);
    const layoutMode = useUiStore((state) => state.wbsLayoutMode);
    const setLayoutMode = useUiStore((state) => state.setWbsLayoutMode);
    const selectedTaskId = useUiStore((state) => state.selectedTaskId);
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);

    const [menu, setMenu] = useState<MenuState>(null);
    const [editingNodeId, setEditingNodeId] = useState<number | null>(null);
    const [draggingTask, setDraggingTask] = useState<TaskCompact | null>(null);
    const [createParentId, setCreateParentId] = useState<number | null | undefined>(undefined);
    const [newSectionTitle, setNewSectionTitle] = useState("");
    const [deleteNodeId, setDeleteNodeId] = useState<number | null>(null);
    const [moveNodeId, setMoveNodeId] = useState<number | null>(null);
    const [moveTaskId, setMoveTaskId] = useState<number | null>(null);
    const [isCreateTaskOpen, setCreateTaskOpen] = useState(false);
    const [isPoolDropTarget, setPoolDropTarget] = useState(false);

    const structureQuery = useQuery({
        queryKey: queryKeys.wbs(project.id),
        queryFn: () => api.get<WbsStructure>(endpoints.wbs(project.id)),
    });
    const stagesQuery = useQuery({
        queryKey: queryKeys.stages(project.id),
        queryFn: () => api.get<ProjectStage[]>(endpoints.projectStages(project.id)),
    });

    const mutations = useWbsMutations(project.id);

    const nodes = useMemo(() => structureQuery.data?.nodes ?? [], [structureQuery.data]);
    const tasks = useMemo(() => structureQuery.data?.tasks ?? [], [structureQuery.data]);
    const tree = useMemo(() => buildWbsTree(nodes, tasks), [nodes, tasks]);

    const handleAssignTask = useCallback(
        (taskId: number, wbsNodeId: number | null) => {
            mutations.assignTask.mutate({ taskId, wbsNodeId });
        },
        [mutations.assignTask],
    );

    const handleRename = useCallback(
        (nodeId: number, title: string) => {
            const trimmed = title.trim();
            const current = nodes.find((node) => node.id === nodeId);
            setEditingNodeId(null);
            if (trimmed !== "" && current !== undefined && trimmed !== current.title) {
                mutations.renameNode.mutate({ nodeId, title: trimmed });
            }
        },
        [nodes, mutations.renameNode],
    );

    const handlers = useMemo<CanvasHandlers>(
        () => ({
            onToggleCollapse: toggleWbsNode,
            onRename: handleRename,
            onCancelRename: () => setEditingNodeId(null),
            onOpenSectionMenu: (nodeId, anchor) => setMenu({ kind: "section", nodeId, anchor }),
            onOpenTaskMenu: (taskId, anchor) => setMenu({ kind: "task", taskId, anchor }),
            onOpenTask: setSelectedTaskId,
            onAssignTask: handleAssignTask,
            onMoveSection: (nodeId, parentId, beforeId) =>
                mutations.moveNode.mutate({ nodeId, parentId, beforeId }),
            onAddRootSection: () => setCreateParentId(null),
        }),
        [
            toggleWbsNode,
            handleRename,
            setSelectedTaskId,
            handleAssignTask,
            mutations.moveNode,
        ],
    );

    function createSection() {
        const title = newSectionTitle.trim();
        if (title === "" || createParentId === undefined) {
            return;
        }
        mutations.createNode.mutate(
            { title, parentId: createParentId },
            {
                onSuccess: (node) => {
                    // Новый раздел остаётся выбранным и сразу доступен для правки (§24 ТЗ).
                    if (createParentId !== null) {
                        expandWbsNodes([createParentId]);
                    }
                    setEditingNodeId(node.id);
                },
            },
        );
        setNewSectionTitle("");
        setCreateParentId(undefined);
    }

    const menuItems = useMemo<ContextMenuItem[]>(() => {
        if (menu === null) {
            return [];
        }
        if (menu.kind === "section") {
            const section = tree.byId.get(menu.nodeId);
            return [
                {
                    key: "add-child",
                    label: "Добавить подраздел",
                    icon: CornerDownRight,
                    onSelect: () => setCreateParentId(menu.nodeId),
                },
                {
                    key: "rename",
                    label: "Переименовать",
                    icon: Pencil,
                    onSelect: () => setEditingNodeId(menu.nodeId),
                },
                {
                    key: "move",
                    label: "Переместить…",
                    icon: Move,
                    onSelect: () => setMoveNodeId(menu.nodeId),
                },
                {
                    key: "collapse",
                    label: collapsed.has(menu.nodeId) ? "Раскрыть ветку" : "Свернуть ветку",
                    icon: collapsed.has(menu.nodeId) ? ChevronsUpDown : ChevronsDownUp,
                    disabled: section === undefined || section.children.length === 0,
                    onSelect: () => toggleWbsNode(menu.nodeId),
                },
                {
                    key: "delete",
                    label: "Удалить раздел",
                    icon: Trash2,
                    tone: "danger",
                    onSelect: () => setDeleteNodeId(menu.nodeId),
                },
            ];
        }
        return [
            {
                key: "open",
                label: "Открыть задачу",
                icon: ExternalLink,
                onSelect: () => setSelectedTaskId(menu.taskId),
            },
            {
                key: "move",
                label: "Переместить в раздел…",
                icon: Move,
                onSelect: () => setMoveTaskId(menu.taskId),
            },
            {
                key: "unassign",
                label: "Убрать из структуры",
                icon: Unlink,
                onSelect: () => handleAssignTask(menu.taskId, null),
            },
        ];
    }, [menu, tree.byId, collapsed, toggleWbsNode, setSelectedTaskId, handleAssignTask]);

    const deleteTarget = deleteNodeId === null ? undefined : tree.byId.get(deleteNodeId);
    const moveTarget = moveNodeId === null ? undefined : tree.byId.get(moveNodeId);
    const moveTask = moveTaskId === null ? undefined : tasks.find((item) => item.id === moveTaskId);
    const allSectionIds = useMemo(
        () => flattenTree(tree.roots).map((item) => item.node.id),
        [tree.roots],
    );
    const isEverythingCollapsed =
        allSectionIds.length > 0 && allSectionIds.every((id) => collapsed.has(id));

    if (structureQuery.isPending || stagesQuery.isPending) {
        return (
            <div className="flex h-full gap-3 p-4">
                <Skeleton className="h-full w-72 shrink-0" />
                <Skeleton className="h-full flex-1" />
            </div>
        );
    }

    if (structureQuery.error) {
        return (
            <div className="p-5">
                <ErrorMessage message={(structureQuery.error as Error).message} />
            </div>
        );
    }

    return (
        <div className="flex h-full min-w-0 flex-col">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2">
                <div className="flex items-center gap-2 text-[12px] text-muted">
                    <span>
                        {structureQuery.data?.stats.total_nodes ?? 0} разделов ·{" "}
                        {structureQuery.data?.stats.assigned_tasks ?? 0} распределено ·{" "}
                        {structureQuery.data?.stats.unassigned_tasks ?? 0} в пуле
                    </span>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                    <div
                        className="flex rounded-md border border-line p-0.5"
                        role="group"
                        aria-label="Режим раскладки"
                    >
                        {(["horizontal", "vertical"] as WbsLayoutMode[]).map((mode) => (
                            <button
                                key={mode}
                                type="button"
                                aria-pressed={layoutMode === mode}
                                onClick={() => setLayoutMode(mode)}
                                className={cn(
                                    "rounded-sm px-2 py-1 text-[11px] font-medium transition-colors",
                                    layoutMode === mode
                                        ? "bg-accent-soft text-accent"
                                        : "text-muted hover:text-secondary",
                                )}
                            >
                                {mode === "horizontal" ? "Горизонтально" : "Вертикально"}
                            </button>
                        ))}
                    </div>

                    <Button
                        size="sm"
                        icon={isEverythingCollapsed ? <ChevronsUpDown size={13} /> : <ChevronsDownUp size={13} />}
                        disabled={allSectionIds.length === 0}
                        onClick={() => {
                            if (isEverythingCollapsed) {
                                expandWbsNodes(allSectionIds);
                            } else {
                                for (const id of allSectionIds) {
                                    if (!collapsed.has(id)) {
                                        toggleWbsNode(id);
                                    }
                                }
                            }
                        }}
                    >
                        {isEverythingCollapsed ? "Раскрыть всё" : "Свернуть всё"}
                    </Button>

                    <Button
                        variant="primary"
                        size="sm"
                        icon={<FolderPlus size={14} />}
                        onClick={() => setCreateParentId(null)}
                    >
                        Раздел
                    </Button>
                </div>
            </div>

            <div
                className="flex min-h-0 flex-1 flex-col lg:flex-row"
                // Страховка: если браузер не прислал dragend, подсказка не должна залипнуть.
                onDrop={() => setDraggingTask(null)}
                onDragEnd={() => setDraggingTask(null)}
            >
                <div
                    onDragOver={(event) => {
                        if (event.dataTransfer.types.includes(TASK_DRAG_TYPE)) {
                            event.preventDefault();
                            setPoolDropTarget(true);
                        }
                    }}
                    onDragLeave={() => setPoolDropTarget(false)}
                    onDrop={(event) => {
                        event.preventDefault();
                        setPoolDropTarget(false);
                        const taskId = Number(event.dataTransfer.getData(TASK_DRAG_TYPE));
                        const dropped = tasks.find((item) => item.id === taskId);
                        if (dropped !== undefined && dropped.wbs_node_id !== null) {
                            handleAssignTask(dropped.id, null);
                        }
                    }}
                    className="flex shrink-0"
                >
                    <TaskPool
                        tasks={tasks}
                        stages={stagesQuery.data ?? []}
                        onOpenTask={setSelectedTaskId}
                        onMoveTask={setMoveTaskId}
                        onCreateTask={() => setCreateTaskOpen(true)}
                        onDragStart={setDraggingTask}
                        onDragEnd={() => {
                            setDraggingTask(null);
                            setPoolDropTarget(false);
                        }}
                        isDropTarget={isPoolDropTarget}
                    />
                </div>

                <div className="min-h-80 min-w-0 flex-1">
                    <StructureCanvas
                        project={project}
                        nodes={nodes}
                        tasks={tasks}
                        stages={stagesQuery.data ?? []}
                        collapsed={collapsed}
                        layoutMode={layoutMode}
                        editingNodeId={editingNodeId}
                        selectedTaskId={selectedTaskId}
                        draggingTask={draggingTask}
                        handlers={handlers}
                    />
                </div>
            </div>

            {menu !== null && (
                <ContextMenu
                    anchor={menu.anchor}
                    items={menuItems}
                    label={menu.kind === "section" ? "Действия раздела" : "Действия задачи"}
                    onClose={() => setMenu(null)}
                />
            )}

            <Modal
                title={createParentId === null ? "Новый раздел" : "Новый подраздел"}
                isOpen={createParentId !== undefined}
                onOpenChange={(open) => {
                    if (!open) {
                        setCreateParentId(undefined);
                        setNewSectionTitle("");
                    }
                }}
                footer={
                    <>
                        <Button onClick={() => setCreateParentId(undefined)}>Отмена</Button>
                        <Button
                            variant="primary"
                            disabled={newSectionTitle.trim() === ""}
                            onClick={createSection}
                        >
                            Создать
                        </Button>
                    </>
                }
            >
                <Field label="Название раздела">
                    {(id) => (
                        <Input
                            id={id}
                            autoFocus
                            value={newSectionTitle}
                            placeholder="Backend"
                            onChange={(event) => setNewSectionTitle(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === "Enter") {
                                    createSection();
                                }
                            }}
                        />
                    )}
                </Field>
            </Modal>

            <Modal
                title={`Удалить раздел «${deleteTarget?.node.title ?? ""}»?`}
                description="Задачи не удаляются — они вернутся в пул нераспределённых."
                isOpen={deleteNodeId !== null}
                onOpenChange={(open) => {
                    if (!open) {
                        setDeleteNodeId(null);
                    }
                }}
                footer={
                    <>
                        <Button onClick={() => setDeleteNodeId(null)}>Отмена</Button>
                        <Button
                            variant="destructive"
                            onClick={() => {
                                if (deleteNodeId !== null) {
                                    mutations.deleteNode.mutate(deleteNodeId);
                                }
                                setDeleteNodeId(null);
                            }}
                        >
                            Удалить и вернуть задачи в пул
                        </Button>
                    </>
                }
            >
                {deleteTarget && (
                    <p className="text-[13px] text-secondary">
                        Раздел содержит: {deleteTarget.children.length} подразделов,{" "}
                        {deleteTarget.progress.total} задач.
                    </p>
                )}
            </Modal>

            {moveTarget && (
                <MoveNodeDialog
                    nodes={nodes}
                    roots={tree.roots}
                    section={moveTarget}
                    isOpen
                    onClose={() => setMoveNodeId(null)}
                    onSubmit={(parentId, beforeId) =>
                        mutations.moveNode.mutate({ nodeId: moveTarget.node.id, parentId, beforeId })
                    }
                />
            )}

            {moveTask && (
                <MoveTaskDialog
                    taskKey={moveTask.key}
                    roots={tree.roots}
                    currentNodeId={moveTask.wbs_node_id}
                    isOpen
                    onClose={() => setMoveTaskId(null)}
                    onSubmit={(wbsNodeId) => handleAssignTask(moveTask.id, wbsNodeId)}
                />
            )}

            <CreateTaskDialog
                projectId={project.id}
                stages={stagesQuery.data ?? []}
                isOpen={isCreateTaskOpen}
                onClose={() => setCreateTaskOpen(false)}
                onCreated={(task) => setSelectedTaskId(task.id)}
            />
        </div>
    );
}
