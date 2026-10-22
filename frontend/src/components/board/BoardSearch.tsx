import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Search, X } from "lucide-react";
import { findBoardObjects } from "@/lib/board/search";
import type { Scene } from "@/lib/board/scene";

interface BoardSearchProps {
    scene: Scene;
    onChoose: (key: string) => void;
    onClose: () => void;
}

export function BoardSearch({ scene, onChoose, onClose }: BoardSearchProps) {
    const [query, setQuery] = useState("");
    const [activeKey, setActiveKey] = useState<string | null>(null);
    const input = useRef<HTMLInputElement>(null);
    const hits = useMemo(() => findBoardObjects(scene, query), [scene, query]);
    const activeIndex = hits.findIndex(hit => hit.key === activeKey);
    useEffect(() => { input.current?.focus(); }, []);
    const choose = (key: string) => {
        setActiveKey(key);
        onChoose(key);
    };
    const step = (direction: number) => {
        if (!hits.length) return;
        const index = activeIndex < 0 ? (direction > 0 ? 0 : hits.length - 1) : (activeIndex + direction + hits.length) % hits.length;
        choose(hits[index].key);
    };
    return (
        <section className="board-search board-panel" data-chosen={activeKey !== null || undefined} role="search" aria-label="Поиск по доске"
            onPointerDown={event => event.stopPropagation()} onKeyDown={event => {
                event.stopPropagation();
                if (event.key === "Escape") { event.preventDefault(); onClose(); }
            }}>
            <div className="board-search__heading">
                <Search size={16} aria-hidden="true" />
                <strong>Поиск по доске</strong>
                <button type="button" className="board-props__btn" aria-label="Закрыть поиск" onClick={onClose}><X size={16} /></button>
            </div>
            <input ref={input} className="board-input" type="search" aria-label="Найти на доске"
                placeholder="Текст стикера, блока или стрелки" maxLength={200} value={query}
                onChange={event => { setQuery(event.target.value); setActiveKey(null); }}
                onKeyDown={event => {
                    if (event.key === "Enter" || event.key === "ArrowDown" || event.key === "ArrowUp") {
                        event.preventDefault();
                        step(event.key === "ArrowUp" || event.shiftKey ? -1 : 1);
                    }
                }} />
            <div className="board-search__navigation">
                <span role="status" aria-label="Результаты поиска">
                    {!query.trim() ? "Введите текст" : !hits.length ? "Ничего не найдено" : activeIndex < 0 ? `Найдено: ${hits.length}` : `${activeIndex + 1} из ${hits.length}`}
                </span>
                <button type="button" className="board-props__btn" disabled={!hits.length} aria-label="Предыдущий результат" onClick={() => step(-1)}><ChevronUp size={16} /></button>
                <button type="button" className="board-props__btn" disabled={!hits.length} aria-label="Следующий результат" onClick={() => step(1)}><ChevronDown size={16} /></button>
            </div>
            <ul className="board-search__results" aria-label="Найденные объекты">
                {hits.slice(0, 100).map(hit => (
                    <li key={hit.key}>
                        <button type="button" className="board-search__result" aria-pressed={hit.key === activeKey}
                            onClick={() => choose(hit.key)}>
                            <span className="board-search__kind">{hit.kind}</span>
                            <span>{hit.text}</span>
                        </button>
                    </li>
                ))}
            </ul>
            {hits.length > 100 && <p className="board-search__hint">Показаны первые 100. Уточните текст или переходите стрелками по всем результатам.</p>}
        </section>
    );
}
