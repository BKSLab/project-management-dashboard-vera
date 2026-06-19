import { useRef, useEffect } from "react";

interface FocusHeadingProps {
    children: React.ReactNode;
    className?: string;
    id?: string;
}

export function FocusHeading({ children, className, id }: FocusHeadingProps) {
    const ref = useRef<HTMLHeadingElement>(null);
    useEffect(() => { ref.current?.focus(); }, []);
    return (
        <h1 ref={ref} id={id} tabIndex={-1} className={`${className ?? ""} focus:outline-none`}>
            {children}
        </h1>
    );
}
