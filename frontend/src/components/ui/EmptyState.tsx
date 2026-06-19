interface EmptyStateProps {
    message: string;
}

export function EmptyState({ message }: EmptyStateProps) {
    return (
        <p role="status" className="py-16 text-center text-muted">
            {message}
        </p>
    );
}
