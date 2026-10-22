import type { ReactNode } from "react";
import {
    Circle,
    Diamond,
    Hand,
    Minus,
    MousePointer2,
    MoveUpRight,
    Square,
    StickyNote,
    Type,
} from "lucide-react";

/** Инструменты доски и горячие клавиши — общий список для панели, справки и клавиатуры. */

export type BoardTool = "select" | "hand" | "rect" | "ellipse" | "diamond" | "arrow" | "line" | "text" | "sticker";

export interface ToolDefinition {
    tool: BoardTool;
    /** event.code — работает при любой раскладке (в том числе русской). */
    code: string;
    key: string;
    label: string;
    hint: string;
    icon: ReactNode;
}

export const TOOLS: ToolDefinition[] = [
    { tool: "select", code: "KeyV", key: "V", label: "Выделение", hint: "Выбрать, двигать и менять размер; рамкой — несколько сразу", icon: <MousePointer2 size={16} aria-hidden="true" /> },
    { tool: "hand", code: "KeyH", key: "H", label: "Рука", hint: "Двигать холст; то же — тянуть правой кнопкой, зажатым колёсиком или с пробелом", icon: <Hand size={16} aria-hidden="true" /> },
    { tool: "rect", code: "KeyR", key: "R", label: "Прямоугольник", hint: "Протяните по холсту; Shift — квадрат", icon: <Square size={16} aria-hidden="true" /> },
    { tool: "ellipse", code: "KeyO", key: "O", label: "Эллипс", hint: "Протяните по холсту; Shift — круг", icon: <Circle size={16} aria-hidden="true" /> },
    { tool: "diamond", code: "KeyD", key: "D", label: "Ромб", hint: "Протяните по холсту; Shift — ровный ромб", icon: <Diamond size={16} aria-hidden="true" /> },
    { tool: "arrow", code: "KeyA", key: "A", label: "Стрелка", hint: "Тяните от фигуры или стикера к другому — концы прилипнут к точкам", icon: <MoveUpRight size={16} aria-hidden="true" /> },
    { tool: "line", code: "KeyL", key: "L", label: "Линия", hint: "Как стрелка, но без наконечника; Shift — угол 45°", icon: <Minus size={16} aria-hidden="true" className="-rotate-45" /> },
    { tool: "text", code: "KeyT", key: "T", label: "Текст", hint: "Кликните или протяните — появится надпись", icon: <Type size={16} aria-hidden="true" /> },
    { tool: "sticker", code: "KeyS", key: "S", label: "Стикер", hint: "Кликните по холсту — стикер встанет в эту точку", icon: <StickyNote size={16} aria-hidden="true" /> },
];

export const SHORTCUTS: { keys: string; action: string }[] = [
    { keys: "V · H · R · O · D · A · L · T · S", action: "Инструменты: выделение, рука, прямоугольник, эллипс, ромб, стрелка, линия, текст, стикер" },
    { keys: "Двойной клик по инструменту", action: "Инструмент «залипает» — можно рисовать подряд" },
    { keys: "Правая кнопка / пробел + тянуть · Shift + колёсико", action: "Двигать холст" },
    { keys: "Колёсико · щипок на тачпаде", action: "Масштаб у курсора" },
    { keys: "На телефоне", action: "Палец по пустому месту — двигать холст; два пальца — двигать и менять масштаб" },
    { keys: "Shift", action: "Квадрат, круг, угол 45°, выделить ещё; при ресайзе — пропорции" },
    { keys: "Alt", action: "Без прилипания к сетке и соседям" },
    { keys: "Тянуть фигуру", action: "Всё, что целиком внутри неё (тексты, фигуры, стикеры), едет вместе; с Ctrl — только сама фигура" },
    { keys: "Двойной клик по фигуре", action: "Подпись; Ctrl+Enter или клик вне — сохранить, Esc — отмена" },
    { keys: "Ctrl+Z · Ctrl+Shift+Z / Ctrl+Y", action: "Отменить · повторить" },
    { keys: "Ctrl+C · Ctrl+V · Ctrl+D", action: "Копировать · вставить · дублировать" },
    { keys: "Ctrl+A", action: "Выделить всё" },
    { keys: "Delete / Backspace", action: "Удалить выделенное" },
    { keys: "Стрелки (Shift — на 8px)", action: "Сдвинуть выделенное" },
    { keys: "Ctrl+] · Ctrl+[", action: "На передний · на задний план" },
    { keys: "Esc", action: "Отменить жест, сбросить инструмент или выделение" },
];
