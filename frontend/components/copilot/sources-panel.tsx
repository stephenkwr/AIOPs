"use client";

import { FileText } from "lucide-react";

import type { Citation } from "@/lib/api/chat";
import { cn } from "@/lib/utils";

export function SourcesPanel({
  citations,
  highlighted,
}: {
  citations: Citation[] | undefined;
  highlighted: number | null;
}) {
  return (
    <aside className="w-full shrink-0 lg:w-80">
      <div className="sticky top-8">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Sources</h2>
        {!citations || citations.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-white py-10 text-center">
            <FileText className="h-6 w-6 text-slate-300" />
            <p className="text-xs text-slate-500">
              Retrieved sources for the latest answer appear here.
            </p>
          </div>
        ) : (
          <ol className="space-y-2">
            {citations.map((c) => (
              <li
                key={c.chunk_id}
                id={`source-${c.index}`}
                className={cn(
                  "rounded-lg border bg-white p-3 transition-colors",
                  highlighted === c.index
                    ? "border-slate-900 ring-1 ring-slate-900"
                    : "border-slate-200",
                )}
              >
                <div className="mb-1 flex items-center gap-2">
                  <span className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-slate-900 px-1 text-[10px] font-semibold text-white">
                    {c.index}
                  </span>
                  <span className="truncate text-xs font-medium text-slate-700">{c.filename}</span>
                  {c.location && <span className="text-[10px] text-slate-400">{c.location}</span>}
                </div>
                <p className="line-clamp-4 text-xs leading-relaxed text-slate-600">{c.snippet}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </aside>
  );
}
