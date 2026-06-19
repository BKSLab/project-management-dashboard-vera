interface ErrorMessageProps {
    title?: string;
    message: string;
}

export function ErrorMessage({
    title = "Ошибка",
    message,
}: ErrorMessageProps) {
    return (
        <div
            role="alert"
            className="rounded border border-red-400/30 bg-red-400/10 px-4 py-3 text-sm text-red-400"
        >
            <p className="font-bold">{title}</p>
            <p>{message}</p>
        </div>
    );
}
