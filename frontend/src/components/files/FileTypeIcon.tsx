import { cn } from "@/lib/cn";
import { fileCategory, fileTypeLabel, type FileDescriptor } from "@/lib/files";

const CATEGORY_STYLES = {
    image: "border-accent-secondary/30 bg-accent-secondary/10 text-accent-secondary",
    pdf: "border-danger/30 bg-danger/10 text-danger",
    word: "border-accent/30 bg-accent/10 text-accent-hover",
    sheet: "border-success/30 bg-success/10 text-success",
    presentation: "border-warning/30 bg-warning/10 text-warning",
    archive: "border-warning/30 bg-warning/10 text-warning",
    text: "border-white/10 bg-white/5 text-muted",
    other: "border-white/10 bg-surface-hover text-muted",
} as const;

export function FileTypeIcon({
    file,
    className,
}: {
    file: Pick<FileDescriptor, "name" | "mime">;
    className?: string;
}) {
    const category = fileCategory(file);

    return (
        <span
            className={cn(
                "relative flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border",
                CATEGORY_STYLES[category],
                className,
            )}
            aria-hidden="true"
        >
            <svg
                width="25"
                height="25"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
            >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                <path d="M14 2v6h6" />
            </svg>
            <span className="absolute bottom-0.5 max-w-[38px] truncate rounded-sm bg-foreground px-1 py-px text-[7px] font-bold leading-none text-background">
                {fileTypeLabel(file)}
            </span>
        </span>
    );
}
