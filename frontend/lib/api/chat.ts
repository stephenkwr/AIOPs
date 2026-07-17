import type { components } from "./schema";

import { api, API_BASE_URL } from "./client";

export type ConversationOut = components["schemas"]["ConversationOut"];

export type Citation = {
  index: number;
  document_id: string;
  chunk_id: string;
  filename: string;
  location: string | null;
  snippet: string;
  score: number;
};

export type ConfidenceParts = {
  retrieval?: number;
  grounded?: number;
  citation_coverage?: number;
  self_score?: number | null;
};

export type AnswerMeta = {
  run_id: string;
  confidence: number | null;
  confidence_parts: ConfidenceParts | null;
  model: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms: number | null;
};

export type AskEvent =
  | { type: "sources"; citations: Citation[] }
  | { type: "token"; text: string }
  | { type: "done"; meta: AnswerMeta }
  | { type: "error"; message: string };

export async function createConversation(title?: string): Promise<ConversationOut> {
  const { data, error } = await api.POST("/api/v1/conversations", {
    body: { title: title ?? null },
  });
  if (error || !data) throw new Error("Failed to create conversation");
  return data;
}

/** Consume the SSE stream from the ask endpoint as typed events. */
export async function* streamAsk(
  conversationId: string,
  question: string,
): AsyncGenerator<AskEvent> {
  const res = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok || !res.body) throw new Error(`Ask failed (${res.status})`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const event = parseSse(raw);
      if (event) yield event;
    }
  }
}

function parseSse(raw: string): AskEvent | null {
  let name = "";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!name) return null;
  const payload = data ? JSON.parse(data) : {};
  switch (name) {
    case "sources":
      return { type: "sources", citations: payload.citations };
    case "token":
      return { type: "token", text: payload.text };
    case "done":
      return { type: "done", meta: payload as AnswerMeta };
    case "error":
      return { type: "error", message: payload.message };
    default:
      return null;
  }
}
