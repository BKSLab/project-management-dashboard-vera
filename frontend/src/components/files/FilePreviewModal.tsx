import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import type { FileDescriptor } from "@/lib/files";
import { FileTypeIcon } from "./FileTypeIcon";

export function FilePreviewModal({
    file,
    onClose,
}: {
    file: FileDescriptor | null;
    onClose: () => void;
}) {
    const [failedPreviewKey, setFailedPreviewKey] = useState<string | null>(null);
    const previewKey = `${file?.key ?? ""}:${file?.url ?? ""}`;
    const loadFailed = failedPreviewKey === previewKey;

    return (
        <Modal
            isOpen={Boolean(file)}
            onOpenChange={(isOpen) => {
                if (!isOpen) onClose();
            }}
            title={file?.name ?? "Изображение"}
            containerClassName="max-h-[calc(100dvh-2rem)] max-w-5xl overflow-y-auto bg-surface/95"
        >
            {file?.url && (
                <div className="flex flex-col gap-3">
                    <div className="flex min-h-52 items-center justify-center overflow-hidden rounded-xl border border-white/[0.07] bg-background">
                        {!loadFailed ? (
                            <img
                                src={file.url}
                                alt={file.name}
                                className="max-h-[72vh] max-w-full object-contain"
                                onError={() => setFailedPreviewKey(previewKey)}
                            />
                        ) : (
                            <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
                                <FileTypeIcon file={file} className="h-14 w-14" />
                                <p className="text-sm text-muted">
                                    Не удалось загрузить изображение для просмотра.
                                </p>
                            </div>
                        )}
                    </div>
                    <div className="flex justify-end">
                        <a
                            href={file.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:border-white/20 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        >
                            Открыть оригинал
                            <svg
                                width="12"
                                height="12"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden="true"
                            >
                                <path d="M14 3h7v7" />
                                <path d="M10 14 21 3" />
                                <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
                            </svg>
                        </a>
                    </div>
                </div>
            )}
        </Modal>
    );
}
