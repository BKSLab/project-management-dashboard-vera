import { useState } from "react";
import type { FileDescriptor } from "@/lib/files";
import { FilePreviewModal } from "./FilePreviewModal";
import { FileTile } from "./FileTile";

export function FileList({
    files,
    onRemove,
    removeDisabled = false,
}: {
    files: FileDescriptor[];
    onRemove?: (file: FileDescriptor) => void;
    removeDisabled?: boolean;
}) {
    const [previewFile, setPreviewFile] = useState<FileDescriptor | null>(null);

    if (files.length === 0) return null;

    return (
        <>
            <div className="flex flex-wrap gap-2">
                {files.map((file) => (
                    <FileTile
                        key={file.key}
                        file={file}
                        onPreview={setPreviewFile}
                        onRemove={onRemove ? () => onRemove(file) : undefined}
                        removeDisabled={removeDisabled}
                    />
                ))}
            </div>
            <FilePreviewModal file={previewFile} onClose={() => setPreviewFile(null)} />
        </>
    );
}
