"use client";

import {
  AlertTriangle,
  ChevronRight,
  Cpu,
  Database,
  Search,
  ShieldAlert,
  ShoppingCart,
  Wrench,
} from "lucide-react";
import { useState } from "react";

import type { RunStep } from "@/lib/api/traces";
import { cn, formatCost, formatLatency } from "@/lib/utils";

type IconType = React.ComponentType<{ className?: string }>;
type TypeMeta = { label: string; icon: IconType; pill: string; bar: string };

const TYPE_META: Record<string, TypeMeta> = {
  retrieval: { label: "Retrieval", icon: Database, pill: "bg-sky-100 text-sky-700", bar: "bg-sky-400" },
  llm_call: { label: "LLM call", icon: Cpu, pill: "bg-violet-100 text-violet-700", bar: "bg-violet-400" },
  tool_call: {
    label: "Tool call",
    icon: Wrench,
    pill: "bg-emerald-100 text-emerald-700",
    bar: "bg-emerald-400",
  },
  approval_wait: {
    label: "Approval",
    icon: ShieldAlert,
    pill: "bg-amber-100 text-amber-700",
    bar: "bg-amber-400",
  },
};

const TOOL_ICON: Record<string, IconType> = {
  search_knowledge_base: Search,
  lookup_order: ShoppingCart,
  create_escalation: AlertTriangle,
};

function iconFor(step: RunStep): IconType {
  if (step.type === "tool_call" || step.type === "approval_wait") {
    return TOOL_ICON[step.name] ?? TYPE_META[step.type]?.icon ?? Wrench;
  }
  return TYPE_META[step.type]?.icon ?? Wrench;
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  if (value == null) return null;
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <pre className="max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-[11px] leading-relaxed text-slate-100">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function StepRow({
  step,
  offsetPct,
  widthPct,
}: {
  step: RunStep;
  offsetPct: number;
  widthPct: number;
}) {
  const [open, setOpen] = useState(false);
  const meta = TYPE_META[step.type] ?? {
    label: step.type,
    icon: Wrench,
    pill: "bg-slate-100 text-slate-600",
    bar: "bg-slate-400",
  };
  const Icon = iconFor(step);
  const failed = step.status === "error" || step.status === "rejected";
  const hasPayload = step.input != null || step.output != null;

  return (
    <li className="rounded-xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => hasPayload && setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-3 px-4 py-3 text-left",
          hasPayload && "hover:bg-slate-50",
        )}
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-500">
          {step.ord}
        </span>
        <Icon className="h-4 w-4 shrink-0 text-slate-500" />
        <span className={cn("shrink-0 rounded-md px-2 py-0.5 text-xs font-medium", meta.pill)}>
          {meta.label}
        </span>
        <span className="truncate font-mono text-xs text-slate-600">{step.name}</span>
        {failed && (
          <span className="shrink-0 rounded-md bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700">
            {step.status}
          </span>
        )}
        <span className="ml-auto flex shrink-0 items-center gap-2 text-xs text-slate-500">
          {step.tokens_in + step.tokens_out > 0 && (
            <span className="tabular-nums" title="Input → output tokens">
              {step.tokens_in}→{step.tokens_out} tok
            </span>
          )}
          {Number(step.cost_usd) > 0 && (
            <span className="tabular-nums">{formatCost(Number(step.cost_usd))}</span>
          )}
          <span className="tabular-nums font-medium text-slate-700">
            {step.latency_ms == null ? "—" : formatLatency(step.latency_ms)}
          </span>
          {hasPayload && (
            <ChevronRight
              className={cn("h-4 w-4 transition-transform", open && "rotate-90")}
            />
          )}
        </span>
      </button>

      {/* Sequential latency waterfall: bar position ∝ when the step ran. */}
      <div className="px-4 pb-3">
        <div className="relative h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className={cn("absolute h-full rounded-full", failed ? "bg-red-400" : meta.bar)}
            style={{ left: `${offsetPct}%`, width: `${widthPct}%` }}
          />
        </div>
      </div>

      {open && hasPayload && (
        <div className="space-y-3 border-t border-slate-100 px-4 py-3">
          <JsonBlock label="Input" value={step.input} />
          <JsonBlock label="Output" value={step.output} />
        </div>
      )}
    </li>
  );
}

export function TraceWaterfall({ steps }: { steps: RunStep[] }) {
  if (steps.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
        No steps were recorded for this run.
      </div>
    );
  }

  const lat = (s: RunStep) => s.latency_ms ?? 0;
  const total = steps.reduce((sum, s) => sum + lat(s), 0) || 1;

  let acc = 0;
  const rows = steps.map((step) => {
    const offset = acc;
    acc += lat(step);
    const widthPct = lat(step) > 0 ? Math.max((lat(step) / total) * 100, 1.5) : 0;
    return { step, offsetPct: (offset / total) * 100, widthPct };
  });

  return (
    <ol className="space-y-2">
      {rows.map(({ step, offsetPct, widthPct }) => (
        <StepRow key={step.id} step={step} offsetPct={offsetPct} widthPct={widthPct} />
      ))}
    </ol>
  );
}
