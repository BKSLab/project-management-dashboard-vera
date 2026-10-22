import { useState } from "react";
import { Pencil } from "lucide-react";
import { Button, IconButton } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";

const TITLE_MAX = 512;

interface TaskTitleEditorProps {
    title: string;
    canEdit: boolean;
    readOnlyHint?: string;
    saving: boolean;
    error?: string;
    /** true — сохранено, правка закрывается; false — ошибка остаётся у поля. */
    onSave: (title: string) => Promise<boolean>;
}

/**
 * Название задачи в шапке карточки: карандаш — правка по месту,
 * Enter — сохранить, Esc — отменить. Пустое название не сохраняется.
 */
export function TaskTitleEditor({ title, canEdit, readOnlyHint, saving, error, onSave }: TaskTitleEditorProps) {
    const [draft, setDraft] = useState<string | null>(null);
    const trimmed = draft?.trim() ?? "";
    const invalid = draft !== null && trimmed === "" ? "Название не может быть пустым" : undefined;

    const submit = async () => {
        if (draft === null || invalid) return;
        if (trimmed === title) {
            setDraft(null);
            return;
        }
        if (await onSave(trimmed)) setDraft(null);
    };

    if (draft === null) {
        return (
            <div className="flex items-start gap-1.5">
                <h2 className="min-w-0 flex-1 text-[15px] leading-snug font-semibold break-words text-primary">{title}</h2>
                {canEdit ? (
                    <IconButton label="Переименовать задачу" size="sm" onClick={() => setDraft(title)}>
                        <Pencil size={13} aria-hidden="true" />
                    </IconButton>
                ) : (
                    readOnlyHint && <span className="sr-only">{readOnlyHint}</span>
                )}
            </div>
        );
    }

    return (
        <form
            className="flex flex-col gap-1.5"
            onSubmit={(event) => {
                event.preventDefault();
                void submit();
            }}
        >
            <Input
                autoFocus
                aria-label="Название задачи"
                value={draft}
                maxLength={TITLE_MAX}
                disabled={saving}
                aria-invalid={Boolean(invalid || error)}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                    if (event.key === "Escape") {
                        // Esc закрывает правку, а не всю карточку.
                        event.preventDefault();
                        event.stopPropagation();
                        setDraft(null);
                    }
                }}
            />
            {(invalid || error) && <p className="text-[12px] text-danger">{invalid ?? error}</p>}
            <div className="flex items-center justify-end gap-2">
                <span className="text-[12px] text-muted mr-auto">Enter — сохранить, Esc — отменить</span>
                <Button size="sm" disabled={saving} onClick={() => setDraft(null)}>
                    Отмена
                </Button>
                <Button size="sm" variant="primary" type="submit" disabled={saving || Boolean(invalid)}>
                    {saving ? "Сохраняем…" : "Сохранить"}
                </Button>
            </div>
        </form>
    );
}
