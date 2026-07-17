import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  awaiting_approval: "bg-amber-100 text-amber-700",
  running: "bg-sky-100 text-sky-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-slate-200 text-slate-600",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
        STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600",
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function ModeBadge({ mode }: { mode: string }) {
  const isAgent = mode === "agent";
  return (
    <span
      className={cn(
        "inline-flex rounded-md px-2 py-0.5 text-xs font-medium",
        isAgent ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600",
      )}
    >
      {isAgent ? "agent" : "chat"}
    </span>
  );
}

export function confidenceTone(value: number): { dot: string; badge: string; label: string } {
  if (value >= 0.7) return { dot: "bg-emerald-500", badge: "bg-emerald-100 text-emerald-700", label: "High" };
  if (value >= 0.4) return { dot: "bg-amber-500", badge: "bg-amber-100 text-amber-700", label: "Medium" };
  return { dot: "bg-red-500", badge: "bg-red-100 text-red-700", label: "Low" };
}

export function ConfidenceDot({ value }: { value: number | null }) {
  if (value == null) return <span className="text-xs text-slate-400">—</span>;
  const tone = confidenceTone(value);
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("h-2 w-2 rounded-full", tone.dot)} />
      <span className="tabular-nums text-xs text-slate-600">{value.toFixed(2)}</span>
    </span>
  );
}
