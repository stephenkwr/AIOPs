"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { getRunTrace } from "@/lib/api/traces";
import { formatCost, formatLatency } from "@/lib/utils";

import { ModeBadge, StatusBadge } from "@/components/traces/badges";
import { ConfidenceBars } from "@/components/traces/confidence-bars";
import { TraceWaterfall } from "@/components/traces/trace-waterfall";

type CitationLike = {
  index: number;
  filename: string;
  location: string | null;
  snippet: string;
};

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-0.5 truncate text-sm font-semibold text-slate-800">{value}</div>
    </div>
  );
}

export default function TraceDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const query = useQuery({
    queryKey: ["run-trace", runId],
    queryFn: () => getRunTrace(runId),
    enabled: Boolean(runId),
  });

  const trace = query.data;
  const citations = (trace?.citations ?? []) as unknown as CitationLike[];

  return (
    <div className="space-y-6">
      <Link
        href="/traces"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="h-4 w-4" /> All traces
      </Link>

      {query.isLoading ? (
        <div className="flex items-center gap-2 py-16 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading trace…
        </div>
      ) : query.isError || !trace ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-8 text-center text-sm text-red-700">
          Couldn&apos;t load this trace.
        </div>
      ) : (
        <>
          <header className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <ModeBadge mode={trace.mode} />
              <StatusBadge status={trace.status} />
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">{trace.question}</h1>
          </header>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <Metric label="Model" value={trace.model ?? "—"} />
            <Metric label="Tokens" value={`${trace.tokens_in} → ${trace.tokens_out}`} />
            <Metric label="Cost" value={formatCost(Number(trace.cost_usd))} />
            <Metric label="Latency" value={formatLatency(trace.latency_ms)} />
            <Metric label="Steps" value={trace.steps.length} />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-3 lg:col-span-2">
              <h2 className="text-sm font-semibold text-slate-700">Trace</h2>
              <TraceWaterfall steps={trace.steps} />
            </div>

            <div className="space-y-4">
              <ConfidenceBars
                confidence={trace.confidence == null ? null : Number(trace.confidence)}
                parts={trace.confidence_parts as Record<string, unknown> | null}
              />
              {trace.failure_reason && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                  <h3 className="text-sm font-semibold text-red-700">Failure</h3>
                  <p className="mt-1 break-words font-mono text-xs text-red-600">
                    {trace.failure_reason}
                  </p>
                </div>
              )}
            </div>
          </div>

          {trace.answer && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="mb-2 text-sm font-semibold text-slate-700">Answer</h2>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
                {trace.answer}
              </p>
              {citations.length > 0 && (
                <ol className="mt-4 space-y-2 border-t border-slate-100 pt-3">
                  {citations.map((c) => (
                    <li key={c.index} className="flex gap-2 text-xs">
                      <span className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-slate-900 px-1 text-[10px] font-semibold text-white">
                        {c.index}
                      </span>
                      <span className="text-slate-600">
                        <span className="font-medium text-slate-700">{c.filename}</span>
                        {c.location && <span className="text-slate-400"> · {c.location}</span>}
                        <span className="mt-0.5 block line-clamp-2 text-slate-500">{c.snippet}</span>
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
