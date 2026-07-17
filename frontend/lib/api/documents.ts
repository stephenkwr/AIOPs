import type { components } from "./schema";

import { api, API_BASE_URL } from "./client";

export type DocumentOut = components["schemas"]["DocumentOut"];

// Statuses that mean "still working" — used to drive live polling in the UI.
export const PROCESSING_STATUSES = ["uploaded", "parsing", "chunking", "embedding"];

export function isProcessing(status: string): boolean {
  return PROCESSING_STATUSES.includes(status);
}

export async function listDocuments(): Promise<DocumentOut[]> {
  const { data, error } = await api.GET("/api/v1/documents");
  if (error || !data) throw new Error("Failed to load documents");
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  const { error } = await api.DELETE("/api/v1/documents/{document_id}", {
    params: { path: { document_id: id } },
  });
  if (error) throw new Error("Failed to delete document");
}

// Multipart upload uses fetch directly (FormData boundary handling) but returns
// the same typed DocumentOut.
export async function uploadDocument(file: File): Promise<DocumentOut> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE_URL}/api/v1/documents`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = `Upload failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return (await res.json()) as DocumentOut;
}
