"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { DocumentsTable } from "@/components/documents-table";
import { UploadDropzone } from "@/components/upload-dropzone";
import { seedDemo } from "@/lib/api/demo";
import { isProcessing, listDocuments } from "@/lib/api/documents";

export default function DocumentsPage() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    // Poll while anything is still ingesting; stop once everything settles.
    refetchInterval: (q) => {
      const docs = q.state.data;
      return docs && docs.some((d) => isProcessing(d.status)) ? 1500 : false;
    },
  });

  const demo = useMutation({
    mutationFn: seedDemo,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload internal docs and support material. Each file is parsed, chunked, and embedded
            into the knowledge base the copilot searches.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            type="button"
            disabled={demo.isPending}
            onClick={() => demo.mutate()}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
            title="Load the Aurora Supply Co. demo knowledge base (12 docs)"
          >
            {demo.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Load demo data
          </button>
          {demo.isSuccess && (
            <span className="text-xs text-slate-500">
              {demo.data.queued > 0
                ? `${demo.data.queued} docs loading — try the Copilot when they're ready.`
                : "Demo data already loaded ✓"}
            </span>
          )}
          {demo.isError && <span className="text-xs text-red-600">Couldn&apos;t load demo data.</span>}
        </div>
      </header>

      <UploadDropzone />

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">Knowledge base</h2>
          {query.data && (
            <span className="text-xs text-slate-500">
              {query.data.length} document{query.data.length === 1 ? "" : "s"}
            </span>
          )}
        </div>
        <DocumentsTable
          documents={query.data}
          isLoading={query.isLoading}
          isError={query.isError}
        />
      </section>
    </div>
  );
}
