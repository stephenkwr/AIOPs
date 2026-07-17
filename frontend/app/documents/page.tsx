"use client";

import { useQuery } from "@tanstack/react-query";

import { DocumentsTable } from "@/components/documents-table";
import { UploadDropzone } from "@/components/upload-dropzone";
import { isProcessing, listDocuments } from "@/lib/api/documents";

export default function DocumentsPage() {
  const query = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    // Poll while anything is still ingesting; stop once everything settles.
    refetchInterval: (q) => {
      const docs = q.state.data;
      return docs && docs.some((d) => isProcessing(d.status)) ? 1500 : false;
    },
  });

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload internal docs and support material. Each file is parsed, chunked, and embedded into
          the knowledge base the copilot searches.
        </p>
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
