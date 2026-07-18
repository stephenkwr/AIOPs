import { cn } from "@/lib/utils";

/** Rates (hit@k, accuracies) read best as percentages. */
export function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

/** Scores (MRR, groundedness, correctness) read best as 0–1. */
export function fmtScore(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toFixed(2);
}

export function EvalModeBadge({ mode }: { mode: string }) {
  const styles: Record<string, string> = {
    keyword: "bg-slate-200 text-slate-700",
    vector: "bg-sky-100 text-sky-700",
    hybrid: "bg-indigo-100 text-indigo-700",
  };
  return (
    <span
      className={cn(
        "inline-flex rounded-md px-2 py-0.5 text-xs font-medium",
        styles[mode] ?? "bg-slate-100 text-slate-600",
      )}
    >
      {mode}
    </span>
  );
}

export function EvalStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-700",
    running: "bg-sky-100 text-sky-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
        styles[status] ?? "bg-slate-100 text-slate-600",
      )}
    >
      {status}
    </span>
  );
}

/** Green/amber/red tint for a 0–1 quality value. */
export function qualityClass(v: number | null | undefined): string {
  if (v == null) return "text-slate-400";
  if (v >= 0.8) return "text-emerald-700";
  if (v >= 0.5) return "text-amber-700";
  return "text-red-700";
}
