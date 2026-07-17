import { cn } from "@/lib/utils";

import { confidenceTone } from "./badges";

export function ConfidenceBars({
  confidence,
  parts,
}: {
  confidence: number | null;
  parts: Record<string, unknown> | null;
}) {
  // null means "never computed" (running / awaiting approval / failed) — don't
  // fabricate a measured 0.00; mirror the list's "—" treatment instead.
  const tone = confidence == null ? null : confidenceTone(confidence);
  const entries = parts
    ? (Object.entries(parts).filter(([, v]) => typeof v === "number") as [string, number][])
    : [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Confidence</h3>
        {confidence == null || tone == null ? (
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
            Not recorded
          </span>
        ) : (
          <span className={cn("rounded-md px-2 py-0.5 text-xs font-medium", tone.badge)}>
            {tone.label} · {confidence.toFixed(2)}
          </span>
        )}
      </div>

      {entries.length === 0 ? (
        <p className="text-xs text-slate-500">No confidence breakdown was recorded for this run.</p>
      ) : (
        <ul className="space-y-2.5">
          {entries.map(([key, value]) => (
            <li key={key}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="capitalize text-slate-600">{key.replace(/_/g, " ")}</span>
                <span className="tabular-nums text-slate-500">{value.toFixed(2)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-slate-800"
                  style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      {confidence != null && (
        <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
          A transparent heuristic — retrieval similarity and citation coverage — shown as-is, not
          a calibrated probability.
        </p>
      )}
    </div>
  );
}
