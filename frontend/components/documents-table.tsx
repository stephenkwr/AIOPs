"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Trash2 } from "lucide-react";

import { deleteDocument, type DocumentOut } from "@/lib/api/documents";
import { fileKindLabel, formatRelativeTime } from "@/lib/utils";

import { StatusBadge } from "./status-badge";

export function DocumentsTable({
  documents,
  isLoading,
  isError,
}: {
  documents: DocumentOut[] | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  const queryClient = useQueryClient();
  const del = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading documents…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-8 text-center text-sm text-red-700">
        Couldn&apos;t reach the API. Is the backend running?
      </div>
    );
  }

  if (!documents || documents.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-slate-200 bg-white py-16 text-center">
        <FileText className="h-8 w-8 text-slate-300" />
        <div className="text-sm font-medium text-slate-700">No documents yet</div>
        <div className="text-xs text-slate-500">Upload a file above to start building the knowledge base.</div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Type</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 text-right font-medium">Chunks</th>
            <th className="px-4 py-3 font-medium">Uploaded</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {documents.map((doc) => (
            <tr key={doc.id} className="hover:bg-slate-50">
              <td className="max-w-[220px] truncate px-4 py-3 font-medium text-slate-800">
                {doc.filename}
              </td>
              <td className="px-4 py-3 text-slate-500">
                {fileKindLabel(doc.mime_type, doc.filename)}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={doc.status} error={doc.error} />
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                {doc.status === "ready" ? doc.chunk_count : "—"}
              </td>
              <td className="px-4 py-3 text-slate-500">{formatRelativeTime(doc.created_at)}</td>
              <td className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={() => del.mutate(doc.id)}
                  disabled={del.isPending}
                  className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                  title="Delete document"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
