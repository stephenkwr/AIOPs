import type { components } from "./schema";

import { api } from "./client";

export type EvalRunSummary = components["schemas"]["EvalRunSummary"];
export type EvalRunDetail = components["schemas"]["EvalRunDetail"];
export type EvalCase = components["schemas"]["EvalCaseOut"];
export type DatasetInfo = components["schemas"]["DatasetInfo"];
export type DatasetItem = components["schemas"]["DatasetItemOut"];

/** Aggregate metrics as the runner writes them (all optional / nullable). */
export type EvalMetrics = {
  n_cases?: number;
  n_answerable?: number;
  n_unanswerable?: number;
  hit_at_k?: number | null;
  mrr?: number | null;
  groundedness?: number | null;
  correctness?: number | null;
  answer_accuracy?: number | null;
  refusal_accuracy?: number | null;
  pass_rate?: number | null;
  n_grading_errors?: number;
};

export function metricsOf(run: { metrics: Record<string, unknown> | null }): EvalMetrics {
  return (run.metrics ?? {}) as EvalMetrics;
}

export async function getDataset(): Promise<DatasetInfo> {
  const { data, error } = await api.GET("/api/v1/eval/dataset");
  if (error || !data) throw new Error("Failed to load dataset");
  return data;
}

export async function listEvalRuns(): Promise<EvalRunSummary[]> {
  const { data, error } = await api.GET("/api/v1/eval/runs");
  if (error || !data) throw new Error("Failed to load eval runs");
  return data;
}

export async function getEvalRun(id: string): Promise<EvalRunDetail> {
  const { data, error } = await api.GET("/api/v1/eval/runs/{run_id}", {
    params: { path: { run_id: id } },
  });
  if (error || !data) throw new Error("Failed to load eval run");
  return data;
}

export async function startEvalRun(opts: {
  retrieval_mode: string;
  graded: boolean;
  k?: number;
}): Promise<EvalRunSummary> {
  const { data, error } = await api.POST("/api/v1/eval/runs", {
    body: { retrieval_mode: opts.retrieval_mode, graded: opts.graded, k: opts.k ?? 8 },
  });
  if (error || !data) throw new Error("Failed to start eval run");
  return data;
}
