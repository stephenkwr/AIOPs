import type { components } from "./schema";

import { api } from "./client";

export type RunSummary = components["schemas"]["RunSummary"];
export type RunStep = components["schemas"]["RunStepOut"];
export type RunTrace = components["schemas"]["RunTrace"];

/** All runs in the workspace (chat + agent), newest first. */
export async function listRuns(): Promise<RunSummary[]> {
  const { data, error } = await api.GET("/api/v1/runs");
  if (error || !data) throw new Error("Failed to load runs");
  return data;
}

/** Full run detail plus its ordered step-by-step trace. */
export async function getRunTrace(runId: string): Promise<RunTrace> {
  const { data, error } = await api.GET("/api/v1/runs/{run_id}/trace", {
    params: { path: { run_id: runId } },
  });
  if (error || !data) throw new Error("Failed to load trace");
  return data;
}
