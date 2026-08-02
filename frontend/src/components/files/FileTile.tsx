import { useState } from "react";
import { cn } from "@/lib/cn";
import { formatFileSize, type FileDescriptor } from "@/lib/files";
import { FileTypeIcon } from "./FileTypeIcon";

export function FileTile({
    file,
    onPreview,
    onRemove,
    removeDisabled = false,
}: {
    file: FileDescriptor;
    onPreview?: (file: FileDescriptor) => void;
    onRemove?: () => void;
    removeDisabled?: boolean;
}) {
    const [failedPreviewKey, setFailedPreviewKey] = useState<string | null>(null);
    const previewKey = `${file.key}:${file.url ?? ""}`;
    const canPreview = Boolean(
        file.previewable && file.url && failedPreviewKey !== previewKey,
    );
    const formattedSize = formatFileSize(file.size);
    const contentClassName = cn(
        "flex min-w-0 flex-1 items-center gap-2.5 rounded-lg text-left",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        file.url && "hover:text-accent-hover",
    );

    const content = (
        <>
            {canPreview ? (
                <img
                    src={file.url!}
                    alt=""
                    loading="lazy"
                    className="h-11 w-11 shrink-0 rounded-lg border border-white/10 bg-surface object-cover"
                    onError={() => setFailedPreviewKey(previewKey)}
                />
            ) : (
                <FileTypeIcon file={file} />
            )}
            <span className="min-w-0 flex-1">
                <span
                    className="block truncate text-xs font-semibold text-foreground"
                    title={file.name}
                >
                    {file.name}
                </span>
                {formattedSize && (
                    <span className="mt-0.5 block text-[10px] font-medium text-muted">
                        {formattedSize}
                    </span>
                )}
            </span>
        </>
    );

    return (
        <div className="relative flex w-[220px] max-w-full items-stretch rounded-xl border border-white/[0.07] bg-surface p-2 shadow-[var(--shadow-card)] transition-colors hover:border-white/15">
            {canPreview && onPreview ? (
                <button
                    type="button"
                    onClick={() => onPreview(file)}
                    className={cn(contentClassName, onRemove && "pr-6")}
                    aria-label={`Открыть изображение ${file.name}`}
                >
                    {content}
                </button>
            ) : file.url ? (
                <a
                    href={file.url}
                    target="_blank"
                    rel="noreferrer"
                    className={cn(contentClassName, onRemove && "pr-6")}
                    aria-label={`Скачать файл ${file.name}`}
                >
                    {content}
                </a>
            ) : (
                <div className={cn(contentClassName, onRemove && "pr-6")}>{content}</div>
            )}
            {onRemove && (
                <button
                    type="button"
                    onClick={onRemove}
                    disabled={removeDisabled}
                    className="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-md text-muted transition-colors hover:bg-danger/10 hover:text-danger focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label={`Удалить файл ${file.name}`}
                    title="Удалить файл"
                >
                    <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                    >
                        <path d="m18 6-12 12M6 6l12 12" />
                    </svg>
                </button>
            )}
        </div>
    );
}
