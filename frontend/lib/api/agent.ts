import type { AnswerMeta, Citation } from "./chat";
import { api, API_BASE_URL } from "./client";

export type AgentStep = {
  type: string;
  name: string;
  status: string;
  tokens_in?: number;
  tokens_out?: number;
  latency_ms?: number;
};

export type ApprovalRequest = {
  approval_id: string;
  run_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  expires_at: string;
};

export type AgentEvent =
  | { type: "run"; run_id: string; conversation_id: string }
  | { type: "step"; step: AgentStep }
  | { type: "sources"; citations: Citation[] }
  | { type: "tool_result"; name: string; status: string; data?: Record<string, unknown> }
  | { type: "approval_required"; approval: ApprovalRequest }
  | { type: "token"; text: string }
  | { type: "done"; meta: AnswerMeta }
  | { type: "error"; message: string };

async function* consume(res: Response): AsyncGenerator<AgentEvent> {
  if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`);
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
      const ev = parse(raw);
      if (ev) yield ev;
    }
  }
}

function parse(raw: string): AgentEvent | null {
  let name = "";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!name) return null;
  const p = data ? JSON.parse(data) : {};
  switch (name) {
    case "run":
      return { type: "run", run_id: p.run_id, conversation_id: p.conversation_id };
    case "step":
      return { type: "step", step: p };
    case "sources":
      return { type: "sources", citations: p.citations };
    case "tool_result":
      return { type: "tool_result", name: p.name, status: p.status, data: p.data };
    case "approval_required":
      return { type: "approval_required", approval: p };
    case "token":
      return { type: "token", text: p.text };
    case "done":
      return { type: "done", meta: p as AnswerMeta };
    case "error":
      return { type: "error", message: p.message };
    default:
      return null;
  }
}

export async function* streamAgent(
  conversationId: string,
  question: string,
): AsyncGenerator<AgentEvent> {
  const res = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}/agent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  yield* consume(res);
}

export async function* streamResume(runId: string): AsyncGenerator<AgentEvent> {
  const res = await fetch(`${API_BASE_URL}/api/v1/runs/${runId}/resume`, { method: "POST" });
  yield* consume(res);
}

export async function decideApproval(
  approvalId: string,
  decision: "approve" | "reject",
  note?: string,
): Promise<void> {
  const { error } = await api.POST("/api/v1/approvals/{approval_id}/decision", {
    params: { path: { approval_id: approvalId } },
    body: { decision, note: note ?? null },
  });
  if (error) throw new Error("Failed to record decision");
}
