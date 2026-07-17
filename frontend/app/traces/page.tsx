"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

import { listRuns } from "@/lib/api/traces";
import { formatCost, formatLatency, formatRelativeTime } from "@/lib/utils";

import { ConfidenceDot, ModeBadge, StatusBadge } from "@/components/traces/badges";

export default function TracesPage() {
  const router = useRouter();
  const query = useQuery({ queryKey: ["runs"], queryFn: listRuns });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Traces</h1>
        <p className="mt-1 text-sm text-slate-500">
          Every run — chat and agent. Open one to see its step-by-step waterfall, token cost, and
          confidence breakdown.
        </p>
      </header>

      {query.isLoading ? (
        <div className="flex items-center gap-2 py-16 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : query.isError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-8 text-center text-sm text-red-700">
          Couldn&apos;t reach the API.
        </div>
      ) : !query.data || query.data.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-slate-200 bg-white py-16 text-center">
          <Activity className="h-8 w-8 text-slate-300" />
          <div className="text-sm font-medium text-slate-700">No runs yet</div>
          <div className="text-xs text-slate-500">Ask the Copilot something to create a trace.</div>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3 font-medium">When</th>
                <th className="px-4 py-3 font-medium">Question</th>
                <th className="px-4 py-3 font-medium">Mode</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Steps</th>
                <th className="px-4 py-3 text-right font-medium">Tokens</th>
                <th className="px-4 py-3 text-right font-medium">Cost</th>
                <th className="px-4 py-3 text-right font-medium">Latency</th>
                <th className="px-4 py-3 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {query.data.map((run) => (
                <tr
                  key={run.id}
                  onClick={() => router.push(`/traces/${run.id}`)}
                  className="cursor-pointer hover:bg-slate-50"
                >
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                    {formatRelativeTime(run.created_at)}
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 text-slate-800">{run.question}</td>
                  <td className="px-4 py-3">
                    <ModeBadge mode={run.mode} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                    {run.step_count}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                    {run.tokens_in + run.tokens_out}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                    {formatCost(Number(run.cost_usd))}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                    {formatLatency(run.latency_ms)}
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceDot value={run.confidence == null ? null : Number(run.confidence)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
