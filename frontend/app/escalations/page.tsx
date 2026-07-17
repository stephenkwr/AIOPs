"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Loader2 } from "lucide-react";

import { listEscalations } from "@/lib/api/ops";
import { cn, formatRelativeTime } from "@/lib/utils";

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-100 text-slate-600",
};

export default function EscalationsPage() {
  const query = useQuery({ queryKey: ["escalations"], queryFn: listEscalations });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Escalations</h1>
        <p className="mt-1 text-sm text-slate-500">
          Tickets the copilot created — each one went through human approval before it was filed.
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
          <AlertTriangle className="h-8 w-8 text-slate-300" />
          <div className="text-sm font-medium text-slate-700">No escalations yet</div>
          <div className="text-xs text-slate-500">
            Ask the Copilot to escalate something, then approve it.
          </div>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3 font-medium">Summary</th>
                <th className="px-4 py-3 font-medium">Priority</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {query.data.map((e) => (
                <tr key={e.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-800">{e.summary}</td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                        PRIORITY_STYLES[e.priority] ?? PRIORITY_STYLES.low,
                      )}
                    >
                      {e.priority}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{e.status}</td>
                  <td className="px-4 py-3 text-slate-500">{formatRelativeTime(e.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
