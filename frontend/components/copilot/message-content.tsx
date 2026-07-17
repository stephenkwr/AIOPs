"use client";

import { cn } from "@/lib/utils";

// Renders assistant text, turning inline [n] markers into clickable citation chips.
export function MessageContent({
  content,
  onCite,
}: {
  content: string;
  onCite?: (index: number) => void;
}) {
  const parts = content.split(/(\[\d+\])/g);
  return (
    <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const index = Number(match[1]);
          return (
            <button
              key={i}
              type="button"
              onClick={() => onCite?.(index)}
              className={cn(
                "mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-slate-200",
                "px-1 align-super text-[10px] font-semibold text-slate-700",
                "transition-colors hover:bg-slate-900 hover:text-white",
              )}
            >
              {index}
            </button>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}
