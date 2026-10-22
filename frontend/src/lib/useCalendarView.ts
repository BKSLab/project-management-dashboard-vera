import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useQueries } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api, endpoints, queryKeys } from "@/lib/api";
import { shiftTimelineAnchor, type HolidayMap, type TimelineRange, type TimelineScale } from "@/lib/calendar";
import {
    calendarHotkey,
    readCalendarViewState,
    shiftGridDate,
    writeCalendarViewParams,
    type CalendarHotkey,
    type CalendarViewDefaults,
    type CalendarViewMode,
    type CalendarViewState,
    type GridScale,
    type StoredCalendarView,
} from "@/lib/calendarGrid";
import type { CalendarHoliday, CalendarHolidays } from "@/lib/types";

/** Настройка отображения (не данные) — последний выбор вида хранится в браузере. */
export function readStored<T>(key: string): T | null {
    try {
        const raw = window.localStorage.getItem(key);
        return raw === null ? null : (JSON.parse(raw) as T);
    } catch {
        return null;
    }
}

export function writeStored(key: string, value: unknown) {
    try {
        window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
        // Хранилище недоступно (приватный режим) — просто не запоминаем.
    }
}

/** Булев выбор отображения с памятью в localStorage (например, открыта ли боковая панель). */
export function useStoredFlag(key: string, initial: boolean): [boolean, (value: boolean) => void] {
    const [value, setValue] = useState(() => readStored<boolean>(key) ?? initial);
    const update = useCallback(
        (next: boolean) => {
            setValue(next);
            writeStored(key, next);
        },
        [key],
    );
    return [value, update];
}

export function useStoredChoice<T extends string>(key: string, allowed: readonly T[], initial: T): [T, (value: T) => void] {
    const [value, setValue] = useState<T>(() => {
        const stored = readStored<string>(key);
        return stored !== null && (allowed as readonly string[]).includes(stored) ? (stored as T) : initial;
    });
    const update = useCallback(
        (next: T) => {
            setValue(next);
            writeStored(key, next);
        },
        [key],
    );
    return [value, update];
}

export function useMediaQuery(query: string): boolean {
    return useSyncExternalStore(
        (notify) => {
            const list = window.matchMedia(query);
            list.addEventListener("change", notify);
            return () => list.removeEventListener("change", notify);
        },
        () => window.matchMedia(query).matches,
        () => false,
    );
}

export const PHONE_QUERY = "(max-width: 767px)";

export interface CalendarViewControls {
    view: CalendarViewMode;
    gridScale: GridScale;
    timelineScale: TimelineScale;
    date: string;
    setView: (view: CalendarViewMode) => void;
    setGridScale: (scale: GridScale, date?: string) => void;
    setTimelineScale: (scale: TimelineScale) => void;
    setDate: (date: string) => void;
    /** Общая дата «Рядом»: сменить день, не выходя из «Уместить проект». */
    focusDate: (date: string) => void;
    /** Сдвиг на период текущего масштаба (стрелки, свайп). */
    shift: (delta: number) => void;
    fit: boolean;
    /** «Уместить проект»: шкала на весь срок в выбранном масштабе; false — обратно к периоду. */
    setFit: (fit: boolean, timelineScale?: TimelineScale) => void;
}

/**
 * Вид календаря в адресе (?view=&scale=&date=) — ссылкой можно поделиться; последний
 * выбор вида и масштаба запоминается в localStorage под `storageKey`. Каждое изменение
 * считается от актуального адреса, а не от состояния прошлой отрисовки: быстрые нажатия
 * горячих клавиш подряд не теряются. `forceView` — вид, навязанный экраном (на телефоне сетка).
 */
export function useCalendarViewState(
    storageKey: string,
    defaults: CalendarViewDefaults,
    today: string,
    forceView?: CalendarViewMode,
): CalendarViewControls {
    const [searchParams, setSearchParams] = useSearchParams();
    const read = useCallback(
        (params: URLSearchParams) => {
            const state = readCalendarViewState(params, readStored<StoredCalendarView>(storageKey), defaults, today);
            return forceView ? { ...state, view: forceView } : state;
        },
        // defaults — литерал страницы; значимы только его поля.
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [storageKey, defaults.view, defaults.gridScale, defaults.timelineScale, today, forceView],
    );
    const state = read(searchParams);

    const update = useCallback(
        (patch: (current: CalendarViewState) => Partial<CalendarViewState>) => {
            // Адрес берём из window.location: роутер отрисовывает переход отложенно, и его
            // searchParams между двумя быстрыми нажатиями ещё прежние.
            const current = new URLSearchParams(window.location.search);
            const base = read(current);
            const next = { ...base, ...patch(base) };
            writeStored(storageKey, { view: next.view, gridScale: next.gridScale, timelineScale: next.timelineScale });
            setSearchParams(
                writeCalendarViewParams(current, {
                    view: next.view,
                    scale: next.view === "timeline" ? next.timelineScale : next.gridScale,
                    tscale: next.timelineScale,
                    date: next.date,
                    fit: next.fit,
                }),
                { replace: true },
            );
        },
        [read, setSearchParams, storageKey],
    );

    return {
        ...state,
        setView: (view) => update(() => ({ view })),
        // В «Рядом» сетка остаётся рядом со шкалой, пока масштаб сетки — неделя или месяц.
        setGridScale: (gridScale, date) =>
            update((current) => ({
                view: current.view === "split" && (gridScale === "week" || gridScale === "month") ? "split" : "grid",
                gridScale,
                date: date ?? current.date,
            })),
        setTimelineScale: (timelineScale) =>
            update((current) => ({ view: current.view === "split" ? "split" : "timeline", timelineScale })),
        setDate: (date) => update(() => ({ date, fit: false })),
        focusDate: (date) => update(() => ({ date })),
        shift: (delta) =>
            update((current) => ({
                fit: false,
                date:
                    current.view === "timeline"
                        ? shiftTimelineAnchor(current.date, current.timelineScale, delta)
                        : shiftGridDate(current.gridScale, current.date, delta),
            })),
        setFit: (fit, timelineScale) =>
            update((current) => ({
                fit,
                view: current.view === "grid" ? "timeline" : current.view,
                timelineScale: timelineScale ?? current.timelineScale,
            })),
    };
}

/** Горячие клавиши страницы календаря; в полях ввода и диалогах не срабатывают. */
export function useCalendarHotkeys(handler: (action: CalendarHotkey) => void, enabled = true) {
    const handlerRef = useRef(handler);
    useLayoutEffect(() => {
        handlerRef.current = handler;
    });
    useEffect(() => {
        if (!enabled) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.defaultPrevented) return;
            const action = calendarHotkey(event);
            if (action === null) return;
            event.preventDefault();
            handlerRef.current(action);
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [enabled]);
}

/**
 * Праздники и переносы за годы видимого периода. Нет ответа (сервис не знает год или
 * недоступен) — в сетке остаются только сб/вс, календарь от этого не ломается.
 */
export function useHolidays(range: TimelineRange): { holidays: HolidayMap; unknownYears: number[] } {
    const firstYear = Number(range.dateFrom.slice(0, 4));
    const lastYear = Number(range.dateTo.slice(0, 4));
    const years = useMemo(() => {
        const list: number[] = [];
        for (let year = firstYear; year <= lastYear && list.length < 3; year += 1) list.push(year);
        return list;
    }, [firstYear, lastYear]);
    const results = useQueries({
        queries: years.map((year) => ({
            queryKey: queryKeys.calendarHolidays(year),
            queryFn: () => api.get<CalendarHolidays>(endpoints.calendarHolidays(year)),
            staleTime: 24 * 60 * 60 * 1000,
            retry: false,
        })),
    });
    const data = results.map((result) => result.data);
    const key = data.map((item) => (item ? `${item.year}:${item.days.length}` : "-")).join("|");
    const holidays = useMemo(() => {
        const map = new Map<string, CalendarHoliday>();
        for (const item of data) {
            for (const day of item?.days ?? []) map.set(day.date, day);
        }
        return map;
        // data меняется по ссылке каждый рендер; пересчитываем по составу ответов.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key]);
    const unknownYears = years.filter((_, index) => {
        const item = data[index];
        return item === undefined ? results[index].isError : !item.known;
    });
    return { holidays, unknownYears };
}
