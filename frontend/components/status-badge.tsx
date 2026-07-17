import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, { label: string; className: string; pulse: boolean }> = {
  uploaded: { label: "Queued", className: "bg-slate-100 text-slate-600", pulse: true },
  parsing: { label: "Parsing", className: "bg-blue-100 text-blue-700", pulse: true },
  chunking: { label: "Chunking", className: "bg-blue-100 text-blue-700", pulse: true },
  embedding: { label: "Embedding", className: "bg-indigo-100 text-indigo-700", pulse: true },
  ready: { label: "Ready", className: "bg-emerald-100 text-emerald-700", pulse: false },
  failed: { label: "Failed", className: "bg-red-100 text-red-700", pulse: false },
};

export function StatusBadge({ status, error }: { status: string; error?: string | null }) {
  const style = STATUS_STYLES[status] ?? {
    label: status,
    className: "bg-slate-100 text-slate-600",
    pulse: false,
  };
  return (
    <span
      title={error ?? undefined}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        style.className,
      )}
    >
      {style.pulse && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {style.label}
    </span>
  );
}
