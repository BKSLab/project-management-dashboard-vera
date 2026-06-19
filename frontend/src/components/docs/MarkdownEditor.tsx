interface MarkdownEditorProps {
    value: string;
    onChange: (value: string) => void;
}

export function MarkdownEditor({ value, onChange }: MarkdownEditorProps) {
    return (
        <div>
            <label htmlFor="markdown-source" className="mb-2 block text-sm font-semibold text-muted">
                Markdown
            </label>
            <textarea
                id="markdown-source"
                value={value}
                onChange={(event) => onChange(event.target.value)}
                spellCheck={false}
                className="h-[70vh] w-full resize-none rounded border border-border bg-surface p-3 font-mono text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            />
        </div>
    );
}
