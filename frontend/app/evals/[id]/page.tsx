"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Check, ChevronRight, Loader2, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

import { type EvalCase, getDataset, getEvalRun, metricsOf } from "@/lib/api/evals";
import { cn } from "@/lib/utils";

import { EvalModeBadge, EvalStatusBadge, fmtPct, fmtScore, qualityClass } from "@/components/evals/ui";

type Filter = "all" | "misses" | "failures";

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-0.5 truncate text-sm font-semibold text-slate-800">{value}</div>
    </div>
  );
}

function CaseRow({ c, referenceAnswer }: { c: EvalCase; referenceAnswer: string | null }) {
  const [open, setOpen] = useState(false);
  const judge = (c.judge ?? {}) as {
    groundedness?: number;
    correctness?: number;
    reasoning?: string;
    error?: string;
  };

  return (
    <li className="rounded-xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50"
      >
        <ChevronRight className={cn("h-4 w-4 shrink-0 text-slate-400 transition-transform", open && "rotate-90")} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm text-slate-800">{c.question}</span>
          <span className="text-[11px] text-slate-400">
            {c.case_id}
            {!c.answerable && " · unanswerable"}
          </span>
        </span>
        {/* retrieval outcome */}
        {c.answerable &&
          (c.hit ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              <Check className="h-3 w-3" /> hit@{c.rank}
            </span>
          ) : (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
              <X className="h-3 w-3" /> miss
            </span>
          ))}
        {c.refused && (
          <span className="shrink-0 rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
            refused
          </span>
        )}
        {judge.groundedness != null && (
          <span className={cn("shrink-0 text-xs tabular-nums", qualityClass(judge.groundedness))}>
            G {fmtScore(judge.groundedness)}
          </span>
        )}
        {judge.correctness != null && (
          <span className={cn("shrink-0 text-xs tabular-nums", qualityClass(judge.correctness))}>
            C {fmtScore(judge.correctness)}
          </span>
        )}
        {c.correct != null &&
          (c.correct ? (
            <Check className="h-4 w-4 shrink-0 text-emerald-600" />
          ) : (
            <X className="h-4 w-4 shrink-0 text-red-600" />
          ))}
      </button>

      {open && (
        <div className="space-y-3 border-t border-slate-100 px-4 py-3 text-sm">
          {c.retrieved && c.retrieved.length > 0 && (
            <div>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                Retrieved (top-{c.retrieved.length})
              </div>
              <ol className="flex flex-wrap gap-1.5">
                {c.retrieved.map((fn, i) => (
                  <li
                    key={`${fn}-${i}`}
                    className={cn(
                      "rounded-md px-2 py-0.5 text-xs",
                      fn === c.gold_doc
                        ? "bg-emerald-100 font-medium text-emerald-800"
                        : "bg-slate-100 text-slate-600",
                    )}
                  >
                    {i + 1}. {fn}
                  </li>
                ))}
              </ol>
              {c.answerable && !c.hit && c.gold_doc && (
                <p className="mt-1 text-xs text-red-600">
                  Gold doc <span className="font-medium">{c.gold_doc}</span> was not retrieved.
                </p>
              )}
            </div>
          )}

          {c.answer && (
            <div>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                Generated answer
              </div>
              <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
                {c.answer}
              </p>
            </div>
          )}

          {referenceAnswer && (
            <div>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                Reference answer
              </div>
              <p className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
                {referenceAnswer}
              </p>
            </div>
          )}

          {judge.reasoning && (
            <div>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                Judge
              </div>
              <p className="text-xs italic text-slate-500">“{judge.reasoning}”</p>
            </div>
          )}
          {judge.error && (
            <p className="text-xs text-red-600">Grading error: {judge.error}</p>
          )}
        </div>
      )}
    </li>
  );
}

export default function EvalRunPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const [filter, setFilter] = useState<Filter>("all");

  const query = useQuery({
    queryKey: ["eval-run", runId],
    queryFn: () => getEvalRun(runId),
    enabled: Boolean(runId),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 2000 : false),
  });
  const dataset = useQuery({ queryKey: ["eval-dataset"], queryFn: getDataset });

  const referenceById = useMemo(() => {
    const map = new Map<string, string>();
    for (const it of dataset.data?.items ?? []) {
      if (it.reference_answer) map.set(it.id, it.reference_answer);
    }
    return map;
  }, [dataset.data]);

  const run = query.data;
  const m = run ? metricsOf(run) : null;

  const cases = useMemo(() => {
    const all = run?.cases ?? [];
    if (filter === "misses") return all.filter((c) => c.answerable && !c.hit);
    if (filter === "failures") return all.filter((c) => c.correct === false);
    return all;
  }, [run, filter]);

  return (
    <div className="space-y-6">
      <Link
        href="/evals"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="h-4 w-4" /> All evaluations
      </Link>

      {query.isLoading ? (
        <div className="flex items-center gap-2 py-16 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading run…
        </div>
      ) : query.isError || !run ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-8 text-center text-sm text-red-700">
          Couldn&apos;t load this evaluation run.
        </div>
      ) : (
        <>
          <header className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <EvalModeBadge mode={run.retrieval_mode} />
              <EvalStatusBadge status={run.status} />
              {run.graded && (
                <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-700">
                  graded
                </span>
              )}
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">{run.label}</h1>
            {run.graded && (
              <p className="text-xs text-slate-500">
                answers: <span className="font-medium">{run.answer_model ?? "—"}</span> · judge:{" "}
                <span className="font-medium">{run.judge_model ?? "—"}</span>
              </p>
            )}
            {run.failure_reason && (
              <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 font-mono text-xs text-red-700">
                {run.failure_reason}
              </p>
            )}
          </header>

          {m && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Metric label={`hit@${run.k}`} value={fmtPct(m.hit_at_k)} />
              <Metric label="MRR" value={fmtScore(m.mrr)} />
              <Metric label="Groundedness" value={fmtScore(m.groundedness)} />
              <Metric label="Correctness" value={fmtScore(m.correctness)} />
              <Metric label="Answer acc." value={fmtPct(m.answer_accuracy)} />
              <Metric label="Refusal acc." value={fmtPct(m.refusal_accuracy)} />
            </div>
          )}

          <div className="flex items-center gap-2">
            {(
              [
                ["all", `All (${run.cases.length})`],
                ["misses", "Retrieval misses"],
                ["failures", "Failed cases"],
              ] as [Filter, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilter(key)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  filter === key
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {cases.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
              Nothing matches this filter — that&apos;s a good sign.
            </div>
          ) : (
            <ol className="space-y-2">
              {cases.map((c) => (
                <CaseRow key={c.id} c={c} referenceAnswer={referenceById.get(c.case_id) ?? null} />
              ))}
            </ol>
          )}
        </>
      )}
    </div>
  );
}
