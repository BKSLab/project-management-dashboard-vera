import { create } from "zustand";

export type WbsLayoutMode = "horizontal" | "vertical";

interface UiState {
    /** Открытая карточка задачи — общая для канбана, списка и структуры. */
    selectedTaskId: number | null;
    setSelectedTaskId: (taskId: number | null) => void;

    sidebarCollapsed: boolean;
    toggleSidebar: () => void;

    /** Свёрнутые ветки ИСР — локальное состояние вида, на backend не уходит. */
    collapsedWbsNodes: Set<number>;
    toggleWbsNode: (nodeId: number) => void;
    expandWbsNodes: (nodeIds: number[]) => void;

    wbsLayoutMode: WbsLayoutMode;
    setWbsLayoutMode: (mode: WbsLayoutMode) => void;
}

export const useUiStore = create<UiState>((set) => ({
    selectedTaskId: null,
    setSelectedTaskId: (taskId) => set({ selectedTaskId: taskId }),

    sidebarCollapsed: false,
    toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

    collapsedWbsNodes: new Set<number>(),
    toggleWbsNode: (nodeId) =>
        set((state) => {
            const next = new Set(state.collapsedWbsNodes);
            if (next.has(nodeId)) {
                next.delete(nodeId);
            } else {
                next.add(nodeId);
            }
            return { collapsedWbsNodes: next };
        }),
    expandWbsNodes: (nodeIds) =>
        set((state) => {
            const next = new Set(state.collapsedWbsNodes);
            for (const nodeId of nodeIds) {
                next.delete(nodeId);
            }
            return { collapsedWbsNodes: next };
        }),

    // ИСР почти всегда рисуют сверху вниз, поэтому это и режим по умолчанию.
    wbsLayoutMode: "vertical",
    setWbsLayoutMode: (mode) => set({ wbsLayoutMode: mode }),
}));
