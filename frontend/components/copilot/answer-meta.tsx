"use client";

import type { AnswerMeta } from "@/lib/api/chat";
import { cn } from "@/lib/utils";

function confidenceLabel(value: number): { label: string; className: string } {
  if (value >= 0.7) return { label: "High", className: "bg-emerald-100 text-emerald-700" };
  if (value >= 0.4) return { label: "Medium", className: "bg-amber-100 text-amber-700" };
  return { label: "Low", className: "bg-red-100 text-red-700" };
}

function Badge({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
    >
      {children}
    </span>
  );
}

export function AnswerMetaRow({ meta }: { meta: AnswerMeta }) {
  const conf = meta.confidence ?? 0;
  const c = confidenceLabel(conf);
  const parts = meta.confidence_parts;
  const confTooltip = parts
    ? `retrieval ${parts.retrieval ?? 0} · citation coverage ${parts.citation_coverage ?? 0}`
    : undefined;

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span
        title={confTooltip}
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
          c.className,
        )}
      >
        Confidence: {c.label} ({conf.toFixed(2)})
      </span>
      {meta.model && <Badge title="Model that served this answer">{meta.model}</Badge>}
      <Badge title="Input → output tokens">
        {meta.tokens_in} → {meta.tokens_out} tok
      </Badge>
      <Badge title="Estimated cost (free-tier models are $0)">${meta.cost_usd.toFixed(4)}</Badge>
      {meta.latency_ms != null && <Badge title="End-to-end latency">{meta.latency_ms} ms</Badge>}
    </div>
  );
}
