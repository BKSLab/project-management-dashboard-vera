import { create } from "zustand";

interface UiState {
    selectedTaskId: number | null;
    setSelectedTaskId: (taskId: number | null) => void;

    drawerOpen: boolean;
    setDrawerOpen: (open: boolean) => void;

    wbsExpandedNodes: Set<number>;
    toggleWbsNode: (nodeId: number) => void;
}

export const useUiStore = create<UiState>((set) => ({
    selectedTaskId: null,
    setSelectedTaskId: (taskId) => set({ selectedTaskId: taskId, drawerOpen: taskId !== null }),

    drawerOpen: false,
    setDrawerOpen: (open) => set({ drawerOpen: open }),

    wbsExpandedNodes: new Set(),
    toggleWbsNode: (nodeId) =>
        set((state) => {
            const next = new Set(state.wbsExpandedNodes);
            if (next.has(nodeId)) {
                next.delete(nodeId);
            } else {
                next.add(nodeId);
            }
            return { wbsExpandedNodes: next };
        }),
}));
