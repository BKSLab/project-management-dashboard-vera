import { Bot } from "lucide-react";
import { cn } from "@/lib/cn";

/** Аватар использует существующий акцент и иконки личного трекера. */
export function TimAvatar({ size = "md", className }: { size?: "sm" | "md"; className?: string }) {
    return <span aria-hidden="true" className={cn("inline-flex shrink-0 items-center justify-center rounded-full border border-ai-border bg-ai-soft text-ai-blue", size === "sm" ? "size-6" : "size-8", className)}><Bot size={size === "sm" ? 16 : 20} /></span>;
}
