import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type ChatPanel = "agent" | "team";
interface ChatDockState {
    projects: Record<number, number>;
    panel: ChatPanel | null;
    selectProject: (userId: number, projectId: number) => void;
    open: (panel: ChatPanel | null) => void;
}
export const useChatDockStore = create<ChatDockState>()(persist((set) => ({
    projects: {}, panel: null,
    selectProject: (userId, projectId) => set((state) => ({ projects: { ...state.projects, [userId]: projectId } })),
    open: (panel) => set({ panel }),
}), { name: "project-chat-dock", storage: createJSONStorage(() => sessionStorage), partialize: (state) => ({ projects: state.projects }) }));
