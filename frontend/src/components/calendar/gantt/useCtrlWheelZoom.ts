import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

/**
 * Ctrl (⌘) + колесо над элементом — смена масштаба шкалы вместо масштаба страницы браузера.
 * Слушатель не пассивный: иначе preventDefault не отменит зум страницы.
 */
export function useCtrlWheelZoom(ref: RefObject<HTMLElement | null>, onZoom: ((direction: number) => void) | undefined) {
    const handlerRef = useRef(onZoom);
    useLayoutEffect(() => {
        handlerRef.current = onZoom;
    });
    const enabled = onZoom !== undefined;
    useEffect(() => {
        const element = ref.current;
        if (!element || !enabled) return;
        let last = 0;
        const onWheel = (event: WheelEvent) => {
            if (!event.ctrlKey && !event.metaKey) return;
            event.preventDefault();
            // Тачпад шлёт десятки событий за жест — один шаг масштаба не чаще раза в 250 мс.
            const now = Date.now();
            if (now - last < 250 || event.deltaY === 0) return;
            last = now;
            handlerRef.current?.(event.deltaY > 0 ? 1 : -1);
        };
        element.addEventListener("wheel", onWheel, { passive: false });
        return () => element.removeEventListener("wheel", onWheel);
    }, [enabled, ref]);
}
