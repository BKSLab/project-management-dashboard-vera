export function SkipLink() {
    return (
        <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-accent-foreground focus:shadow-lg focus:outline-2 focus:outline-offset-2 focus:outline-accent"
        >
            Перейти к содержимому
        </a>
    );
}
