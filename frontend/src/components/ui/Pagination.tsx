interface PaginationProps {
    currentPage: number;
    totalPages: number;
    onPageChange: (page: number) => void;
}

const ChevronLeft = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M15 18l-6-6 6-6" />
    </svg>
);

const ChevronRight = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M9 18l6-6-6-6" />
    </svg>
);

const baseBtn =
    "inline-flex h-10 min-w-[2.5rem] items-center justify-center rounded-md px-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-40";

const idleBtn =
    "border border-white/15 bg-white/5 text-foreground hover:border-accent/60 hover:bg-white/10";

const activeBtn =
    "bg-accent text-accent-foreground font-bold cursor-default";

export function Pagination({
    currentPage,
    totalPages,
    onPageChange,
}: PaginationProps) {
    if (totalPages <= 1) return null;

    const start = Math.max(1, currentPage - 2);
    const end = Math.min(totalPages, currentPage + 2);
    const pages: number[] = [];
    for (let i = start; i <= end; i++) pages.push(i);

    return (
        <nav
            aria-label="Пагинация"
            className="flex flex-wrap items-center justify-center gap-1.5 py-8"
        >
            <button
                onClick={() => onPageChange(currentPage - 1)}
                disabled={currentPage === 1}
                aria-label="Предыдущая страница"
                className={`${baseBtn} ${idleBtn}`}
            >
                <ChevronLeft />
            </button>

            {start > 1 && (
                <>
                    <button
                        onClick={() => onPageChange(1)}
                        aria-label="Страница 1"
                        className={`${baseBtn} ${idleBtn}`}
                    >
                        1
                    </button>
                    {start > 2 && (
                        <span
                            className="inline-flex h-10 min-w-[2.5rem] select-none items-center justify-center text-sm text-muted"
                            aria-hidden="true"
                        >
                            …
                        </span>
                    )}
                </>
            )}

            {pages.map((page) => (
                <button
                    key={page}
                    onClick={() => page !== currentPage ? onPageChange(page) : undefined}
                    aria-current={page === currentPage ? "page" : undefined}
                    className={`${baseBtn} ${page === currentPage ? activeBtn : idleBtn}`}
                >
                    <span className="sr-only">Страница </span>{page}
                </button>
            ))}

            {end < totalPages && (
                <>
                    {end < totalPages - 1 && (
                        <span
                            className="inline-flex h-10 min-w-[2.5rem] select-none items-center justify-center text-sm text-muted"
                            aria-hidden="true"
                        >
                            …
                        </span>
                    )}
                    <button
                        onClick={() => onPageChange(totalPages)}
                        className={`${baseBtn} ${idleBtn}`}
                    >
                        <span className="sr-only">Страница </span>{totalPages}
                    </button>
                </>
            )}

            <button
                onClick={() => onPageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                aria-label="Следующая страница"
                className={`${baseBtn} ${idleBtn}`}
            >
                <ChevronRight />
            </button>
        </nav>
    );
}
