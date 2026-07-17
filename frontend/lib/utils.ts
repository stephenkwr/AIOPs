export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const s = Math.round(diffMs / 1000);
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function fileKindLabel(mime: string, filename: string): string {
  const ext = filename.includes(".") ? filename.split(".").pop()!.toLowerCase() : "";
  if (mime.includes("pdf") || ext === "pdf") return "PDF";
  if (mime.includes("html") || ext === "html" || ext === "htm") return "HTML";
  if (mime.includes("csv") || ext === "csv") return "CSV";
  if (ext === "md") return "MD";
  return "TXT";
}
