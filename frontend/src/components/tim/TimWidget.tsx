import { Suspense, lazy } from "react";
import "./tim.css";
import { TimAvatar } from "./TimAvatar";
import { useCurrentUser } from "@/lib/useAuth";
import { useChatDockStore } from "@/stores/chatDock";
import { useTimWidgetStore } from "@/stores/timWidget";
import { TIM_NAME, TIM_PERSONA } from "@/lib/tim";

// Панель с перепиской грузится при первом открытии — не утяжеляет старт.
const TimPanel = lazy(() => import("./TimPanel").then((module) => ({ default: module.TimPanel })));

const FAB_ID = "tt-tim-fab";

/** Общий помощник с отдельной сохранённой перепиской. */
export function TimWidget() {
    const open = useTimWidgetStore((state) => state.open);
    const setOpen = useTimWidgetStore((state) => state.setOpen);
    const dockPanel = useChatDockStore((state) => state.panel);
    const userId = useCurrentUser().data?.id;
    if (!userId) return null;
    const toggle = () => {
        if (!open) useChatDockStore.getState().open(null);
        setOpen(!open);
    };
    return <div data-react-aria-top-layer="true" className="tt-tim">
        {open && <Suspense fallback={null}><TimPanel userId={userId} onClose={() => { setOpen(false); requestAnimationFrame(() => document.getElementById(FAB_ID)?.focus()); }} /></Suspense>}
        {!open && !dockPanel && <button id={FAB_ID} type="button" className="tt-tim-fab" onClick={toggle} aria-expanded={false} aria-label="Спросить Веру"
            title={`${TIM_PERSONA}: спросите о ваших задачах, сроках и проектах. Она видит страницу, на которой вы находитесь`}>
            <TimAvatar size="sm" />
            <span aria-hidden="true">{TIM_NAME}</span>
        </button>}
    </div>;
}
