"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Loader2, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { getDataset, listEvalRuns, metricsOf, startEvalRun } from "@/lib/api/evals";
import { formatRelativeTime } from "@/lib/utils";

import { ComparePanel } from "@/components/evals/compare-panel";
import { EvalModeBadge, EvalStatusBadge, fmtPct, fmtScore } from "@/components/evals/ui";

export default function EvalsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [mode, setMode] = useState("hybrid");
  const [graded, setGraded] = useState(false);

  const dataset = useQuery({ queryKey: ["eval-dataset"], queryFn: getDataset });
  const runs = useQuery({
    queryKey: ["eval-runs"],
    queryFn: listEvalRuns,
    // Poll while any run is in flight so metrics appear as they land.
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 2000 : false),
  });

  const launch = useMutation({
    mutationFn: () => startEvalRun({ retrieval_mode: mode, graded }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["eval-runs"] }),
  });

  const ds = dataset.data;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Evaluation</h1>
        <p className="mt-1 text-sm text-slate-500">
          A version-controlled golden dataset scored against the live retrieval pipeline —
          run a configuration, then compare before/after.
        </p>
      </header>

      {ds && (
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">
            dataset: <span className="font-medium">{ds.name}</span>
          </span>
          <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">
            {ds.total} questions
          </span>
          <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">
            {ds.answerable} answerable
          </span>
          <span className="rounded-md bg-amber-50 px-2 py-1 text-amber-700">
            {ds.unanswerable} unanswerable (should refuse)
          </span>
          <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">
            {ds.corpus_docs.length} corpus docs
          </span>
        </div>
      )}

      {/* Launcher */}
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-700">Run an evaluation</h2>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            Retrieval
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
            >
              <option value="keyword">keyword (baseline)</option>
              <option value="vector">vector</option>
              <option value="hybrid">hybrid (production)</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={graded}
              onChange={(e) => setGraded(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            Grade answers (LLM-as-judge — slower, uses the live models)
          </label>
          <button
            type="button"
            disabled={launch.isPending}
            onClick={() => launch.mutate()}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
          >
            {launch.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run
          </button>
          {launch.isError && (
            <span className="text-sm text-red-600">Couldn&apos;t start the run.</span>
          )}
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Retrieval-only runs finish in seconds. Graded runs generate and judge an answer for
          every question (~2–4 min on free-tier limits).
        </p>
      </section>

      {runs.data && <ComparePanel runs={runs.data} />}

      {/* Runs table */}
      {runs.isLoading ? (
        <div className="flex items-center gap-2 py-16 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : runs.isError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-8 text-center text-sm text-red-700">
          Couldn&apos;t reach the API.
        </div>
      ) : !runs.data || runs.data.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-slate-200 bg-white py-16 text-center">
          <FlaskConical className="h-8 w-8 text-slate-300" />
          <div className="text-sm font-medium text-slate-700">No evaluation runs yet</div>
          <div className="text-xs text-slate-500">Launch one above to get a baseline.</div>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3 font-medium">When</th>
                <th className="px-4 py-3 font-medium">Run</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">hit@k</th>
                <th className="px-4 py-3 text-right font-medium">MRR</th>
                <th className="px-4 py-3 text-right font-medium">Answer acc.</th>
                <th className="px-4 py-3 text-right font-medium">Refusal acc.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.data.map((r) => {
                const m = metricsOf(r);
                return (
                  <tr
                    key={r.id}
                    onClick={() => router.push(`/evals/${r.id}`)}
                    className="cursor-pointer hover:bg-slate-50"
                  >
                    <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                      {formatRelativeTime(r.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <EvalModeBadge mode={r.retrieval_mode} />
                        <span className="text-slate-800">{r.label}</span>
                        {r.graded && (
                          <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-700">
                            graded
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <EvalStatusBadge status={r.status} />
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-800">
                      {fmtPct(m.hit_at_k)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                      {fmtScore(m.mrr)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                      {fmtPct(m.answer_accuracy)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                      {fmtPct(m.refusal_accuracy)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
