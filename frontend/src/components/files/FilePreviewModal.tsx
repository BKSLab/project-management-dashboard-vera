import { useState } from "react";
import { Download, ExternalLink } from "lucide-react";
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

    if (!file) {
        return null;
    }

    return (
        <Modal
            isOpen
            size="lg"
            title={file.name}
            onOpenChange={(isOpen) => {
                if (!isOpen) {
                    onClose();
                }
            }}
            footer={
                file.url ? (
                    <>
                        <a
                            href={file.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line bg-surface-2 px-3 text-[13px] font-medium text-primary hover:border-line-strong hover:bg-hover"
                        >
                            Открыть оригинал
                            <ExternalLink size={13} aria-hidden="true" />
                        </a>
                        <a
                            href={file.url}
                            download={file.name}
                            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-accent px-3 text-[13px] font-semibold text-[#0d1117] hover:bg-accent-hover"
                        >
                            Скачать
                            <Download size={13} aria-hidden="true" />
                        </a>
                    </>
                ) : undefined
            }
        >
            {file.url && (
                <div className="flex min-h-52 items-center justify-center overflow-hidden rounded-lg border border-line bg-app">
                    {!loadFailed ? (
                        <img
                            src={file.url}
                            alt={file.name}
                            className="max-h-[62vh] max-w-full object-contain"
                            onError={() => setFailedPreviewKey(previewKey)}
                        />
                    ) : (
                        <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
                            <FileTypeIcon file={file} className="h-14 w-14" />
                            <p className="text-[13px] text-muted">
                                Не удалось загрузить изображение для просмотра.
                            </p>
                        </div>
                    )}
                </div>
            )}
        </Modal>
    );
}
