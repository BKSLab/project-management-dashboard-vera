import { useState } from "react";
import type { Alignment, DistributionAxis } from "@/lib/board/layout";

export interface BoardActionsProps {
    selectedCount: number;
    editable: boolean;
    busy?: boolean;
    hasLockedSelection: boolean;
    hasGroupSelection: boolean;
    canCreateProject?: boolean;
    templates: { id: string; name: string }[];
    onAlign: (alignment: Alignment) => void;
    onDistribute: (axis: DistributionAxis) => void;
    onGroup: (name: string) => void;
    onUngroup: () => void;
    onSetLocked: (locked: boolean) => void;
    onSaveTemplate: (name: string) => void;
    onInsertTemplate: (id: string) => void;
    onDeleteTemplate: (id: string) => void;
    onExport: (format: "png" | "svg", scope: "board" | "selection") => void;
    onCreateProject?: () => void;
}

const ALIGNMENTS: [Alignment, string][] = [
    ["left", "По левому краю"], ["center", "По центру горизонтали"], ["right", "По правому краю"],
    ["top", "По верхнему краю"], ["middle", "По центру вертикали"], ["bottom", "По нижнему краю"],
];

/** Controlled callbacks; parent owns history, persistence, error UI and the mixed batch. */
export function BoardActions(props: BoardActionsProps) {
    const [name, setName] = useState("");
    const [templateId, setTemplateId] = useState("");
    const [scope, setScope] = useState<"board" | "selection">("board");
    const busy = Boolean(props.busy);
    const canMutate = props.editable && !busy;
    const canMove = canMutate && !props.hasLockedSelection;
    const selectedTemplate = props.templates.some((item) => item.id === templateId) ? templateId : "";
    return (
        <section className="board-panel" aria-label="Действия с доской">
            <div className="board-panel-heading">Инструменты доски</div>
            <div className="board-scroll">
                <fieldset disabled={!canMove || props.selectedCount < 2}>
                    <legend>Выравнивание выделения</legend>
                    <p>Группа двигается целиком. Заблокированные объекты остаются на месте.</p>
                    {ALIGNMENTS.map(([alignment, label]) => (
                        <button className="board-button" type="button" key={alignment} title={label}
                            onClick={() => props.onAlign(alignment)}>{label}</button>
                    ))}
                    <button className="board-button" type="button" disabled={props.selectedCount < 3}
                        title="Равные промежутки между краями объектов; крайние остаются на месте"
                        onClick={() => props.onDistribute("horizontal")}>Равные интервалы по горизонтали</button>
                    <button className="board-button" type="button" disabled={props.selectedCount < 3}
                        title="Равные промежутки между краями объектов; крайние остаются на месте"
                        onClick={() => props.onDistribute("vertical")}>Равные интервалы по вертикали</button>
                </fieldset>
                <fieldset disabled={!canMutate}>
                    <legend>Группы и блокировка</legend>
                    <label>Название группы или шаблона
                        <input className="board-input" maxLength={120} value={name}
                            onChange={(event) => setName(event.target.value)} />
                    </label>
                    <button className="board-button" type="button" disabled={!canMove || props.selectedCount < 2 || !name.trim()}
                        title="Объединить выделение в явную группу"
                        onClick={() => props.onGroup(name.trim())}>Сгруппировать</button>
                    <button className="board-button" type="button" disabled={!canMove || !props.hasGroupSelection}
                        title="Разделить группу на отдельные объекты"
                        onClick={props.onUngroup}>Разгруппировать</button>
                    <button className="board-button" type="button" disabled={props.selectedCount === 0}
                        title={props.hasLockedSelection ? "Разрешить редактирование выделения" : "Защитить выделение от случайных изменений"}
                        onClick={() => props.onSetLocked(!props.hasLockedSelection)}>
                        {props.hasLockedSelection ? "Разблокировать" : "Заблокировать"}
                    </button>
                    <p>Блокировка защищает от случайной правки. Это не ограничение доступа.</p>
                </fieldset>
                <fieldset disabled={!canMutate}>
                    <legend>Шаблоны</legend>
                    <p>Шаблон сохраняет объекты и связи внутри выделения. Привязки к задачам в него не входят.</p>
                    <button className="board-button" type="button" disabled={!name.trim() || props.selectedCount === 0}
                        title="Сохранить выделение как шаблон этой доски"
                        onClick={() => props.onSaveTemplate(name.trim())}>Сохранить выделение как шаблон</button>
                    <label>Шаблон доски
                        <select className="board-input" aria-label="Шаблон доски" value={selectedTemplate} onChange={(event) => setTemplateId(event.target.value)}>
                            <option value="">Выберите шаблон</option>
                            {props.templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
                        </select>
                    </label>
                    <button className="board-button" type="button" disabled={!selectedTemplate}
                        title="Вставить весь шаблон одним действием с возможностью отмены"
                        onClick={() => props.onInsertTemplate(selectedTemplate)}>Вставить шаблон</button>
                    <button className="board-button" type="button" disabled={!selectedTemplate}
                        title="Удалить только шаблон; объекты на доске сохранятся"
                        onClick={() => props.onDeleteTemplate(selectedTemplate)}>Удалить шаблон</button>
                </fieldset>
                <fieldset disabled={busy}>
                    <legend>Экспорт</legend>
                    <label>Что выгрузить
                        <select className="board-input" aria-label="Что выгрузить" value={scope} onChange={(event) => setScope(event.target.value as "board" | "selection")}>
                            <option value="board">Всю доску</option>
                            <option value="selection" disabled={props.selectedCount === 0}>Выделение</option>
                        </select>
                    </label>
                    <p>В файл попадут и объекты за пределами видимой области.</p>
                    {(["png", "svg"] as const).map((format) => (
                        <button className="board-button" key={format} type="button"
                            disabled={scope === "selection" && props.selectedCount === 0}
                            title={format === "svg" ? "Векторный файл для печати и редактирования" : "Изображение для отправки"}
                            onClick={() => props.onExport(format, scope)}>Выгрузить {format.toUpperCase()}</button>
                    ))}
                </fieldset>
                {props.canCreateProject && props.onCreateProject && (
                    <button className="board-button board-button--primary" type="button" disabled={!canMutate}
                        title="Создать проект из этой личной доски. Доска и все объекты сохранят свои идентификаторы."
                        onClick={props.onCreateProject}>Создать проект из доски</button>
                )}
            </div>
        </section>
    );
}
