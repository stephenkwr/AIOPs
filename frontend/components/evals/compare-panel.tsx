"use client";

import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";

import { type EvalRunSummary, metricsOf } from "@/lib/api/evals";
import { cn } from "@/lib/utils";

import { EvalModeBadge, fmtPct, fmtScore } from "./ui";

type MetricRow = {
  key: keyof ReturnType<typeof metricsOf>;
  label: string;
  fmt: (v: number | null | undefined) => string;
};

const ROWS: MetricRow[] = [
  { key: "hit_at_k", label: "Retrieval hit@k", fmt: fmtPct },
  { key: "mrr", label: "MRR", fmt: fmtScore },
  { key: "groundedness", label: "Groundedness", fmt: fmtScore },
  { key: "correctness", label: "Correctness", fmt: fmtScore },
  { key: "answer_accuracy", label: "Answer accuracy", fmt: fmtPct },
  { key: "refusal_accuracy", label: "Refusal accuracy", fmt: fmtPct },
  { key: "pass_rate", label: "Overall pass rate", fmt: fmtPct },
];

function runName(r: EvalRunSummary): string {
  return `${r.label} — ${new Date(r.created_at).toLocaleString()}`;
}

export function ComparePanel({ runs }: { runs: EvalRunSummary[] }) {
  const completed = runs.filter((r) => r.status === "completed");
  const [baselineId, setBaselineId] = useState<string>("");
  const [candidateId, setCandidateId] = useState<string>("");

  // Sensible defaults: latest keyword run as the "before", latest non-keyword as
  // "after" — never the same run on both sides. A selection whose run
  // disappeared from the list re-defaults.
  useEffect(() => {
    if (completed.length < 2) return;
    const exists = (id: string) => completed.some((r) => r.id === id);

    let base = baselineId && exists(baselineId) ? baselineId : "";
    if (!base) {
      const kw = completed.find((r) => r.retrieval_mode === "keyword");
      base = (kw ?? completed[completed.length - 1]).id;
      setBaselineId(base);
    }
    if (!candidateId || !exists(candidateId)) {
      const other =
        completed.find((r) => r.retrieval_mode !== "keyword" && r.id !== base) ??
        completed.find((r) => r.id !== base) ??
        completed[0];
      setCandidateId(other.id);
    }
  }, [completed, baselineId, candidateId]);

  if (completed.length < 2) return null;

  const baseline = completed.find((r) => r.id === baselineId);
  const candidate = completed.find((r) => r.id === candidateId);
  if (!baseline || !candidate) return null;

  const mA = metricsOf(baseline);
  const mB = metricsOf(candidate);
  const visible = ROWS.filter((row) => mA[row.key] != null || mB[row.key] != null);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-700">Before / after</h2>
      <p className="mt-0.5 text-xs text-slate-500">
        Same golden dataset, two configurations — the delta is the improvement.
      </p>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
        <select
          value={baselineId}
          onChange={(e) => setBaselineId(e.target.value)}
          className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs sm:w-72"
        >
          {completed.map((r) => (
            <option key={r.id} value={r.id}>
              baseline: {runName(r)}
            </option>
          ))}
        </select>
        <ArrowRight className="hidden h-4 w-4 shrink-0 text-slate-400 sm:block" />
        <select
          value={candidateId}
          onChange={(e) => setCandidateId(e.target.value)}
          className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs sm:w-72"
        >
          {completed.map((r) => (
            <option key={r.id} value={r.id}>
              candidate: {runName(r)}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-4 font-medium">Metric</th>
              <th className="py-2 pr-4 font-medium">
                <span className="inline-flex items-center gap-1.5">
                  Baseline <EvalModeBadge mode={baseline.retrieval_mode} />
                </span>
              </th>
              <th className="py-2 pr-4 font-medium">
                <span className="inline-flex items-center gap-1.5">
                  Candidate <EvalModeBadge mode={candidate.retrieval_mode} />
                </span>
              </th>
              <th className="py-2 font-medium">Δ</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visible.map((row) => {
              const a = mA[row.key] as number | null | undefined;
              const b = mB[row.key] as number | null | undefined;
              const delta = a != null && b != null ? b - a : null;
              return (
                <tr key={row.key}>
                  <td className="py-2 pr-4 text-slate-600">{row.label}</td>
                  <td className="py-2 pr-4 tabular-nums text-slate-800">{row.fmt(a)}</td>
                  <td className="py-2 pr-4 tabular-nums font-medium text-slate-900">
                    {row.fmt(b)}
                  </td>
                  <td
                    className={cn(
                      "py-2 tabular-nums font-medium",
                      delta == null
                        ? "text-slate-400"
                        : delta > 0.0005
                          ? "text-emerald-700"
                          : delta < -0.0005
                            ? "text-red-700"
                            : "text-slate-500",
                    )}
                  >
                    {delta == null ? "—" : `${delta > 0 ? "+" : ""}${row.fmt(delta)}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
