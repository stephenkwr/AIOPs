"use client";

import { Check, Loader2, ShieldAlert, X } from "lucide-react";
import { useState } from "react";

import type { ApprovalRequest } from "@/lib/api/agent";

const TOOL_LABELS: Record<string, string> = {
  create_escalation: "Create escalation ticket",
};

export type ApprovalState = ApprovalRequest & {
  decision?: "approved" | "rejected";
  deciding?: boolean;
};

export function ApprovalCard({
  approval,
  onDecide,
}: {
  approval: ApprovalState;
  onDecide: (decision: "approve" | "reject", note?: string) => void;
}) {
  const [note, setNote] = useState("");
  const label = TOOL_LABELS[approval.tool_name] ?? approval.tool_name;
  const decided = approval.decision !== undefined;

  return (
    <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-4">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-amber-600" />
        <span className="text-sm font-semibold text-amber-800">Action needs your approval</span>
      </div>

      <p className="mt-2 text-sm text-slate-700">
        The copilot wants to <span className="font-medium">{label}</span>:
      </p>
      <dl className="mt-2 space-y-1 rounded-lg bg-white/70 p-3 text-xs">
        {Object.entries(approval.tool_args).map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="min-w-24 font-medium text-slate-500">{k}</dt>
            <dd className="text-slate-800">{String(v)}</dd>
          </div>
        ))}
      </dl>

      {decided ? (
        <div className="mt-3 text-sm font-medium">
          {approval.decision === "approved" ? (
            <span className="text-emerald-700">✓ Approved — executing…</span>
          ) : (
            <span className="text-red-700">✕ Rejected — the copilot will adapt.</span>
          )}
        </div>
      ) : (
        <>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional note (shown to the copilot on reject)…"
            className="mt-3 w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs outline-none focus:border-slate-500"
          />
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={approval.deciding}
              onClick={() => onDecide("approve", note || undefined)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {approval.deciding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              Approve
            </button>
            <button
              type="button"
              disabled={approval.deciding}
              onClick={() => onDecide("reject", note || undefined)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <X className="h-4 w-4" />
              Reject
            </button>
          </div>
        </>
      )}
    </div>
  );
}
