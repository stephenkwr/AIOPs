"use client";

import { Loader2, SendHorizonal } from "lucide-react";
import { useRef, useState } from "react";

import {
  type AgentEvent,
  type AgentStep,
  decideApproval,
  streamAgent,
  streamResume,
} from "@/lib/api/agent";
import { type AnswerMeta, type Citation, createConversation } from "@/lib/api/chat";
import { cn } from "@/lib/utils";

import { AnswerMetaRow } from "./answer-meta";
import { ApprovalCard, type ApprovalState } from "./approval-card";
import { MessageContent } from "./message-content";
import { SourcesPanel } from "./sources-panel";
import { StepTrail } from "./step-trail";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps: AgentStep[];
  citations?: Citation[];
  approval?: ApprovalState;
  meta?: AnswerMeta;
  runId?: string;
  streaming?: boolean;
  error?: string;
};

const EXAMPLES = [
  "How do I reset my password?",
  "What's the status of order 1042?",
  "Please escalate a billing dispute for order 1043 to a human.",
];

function patch(messages: ChatMessage[], id: string, fn: (m: ChatMessage) => ChatMessage) {
  return messages.map((m) => (m.id === id ? fn(m) : m));
}

export function ChatView() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const conversationId = useRef<string | null>(null);

  function applyEvent(id: string, ev: AgentEvent) {
    setMessages((m) =>
      patch(m, id, (x) => {
        switch (ev.type) {
          case "run":
            return { ...x, runId: ev.run_id };
          case "step":
            return x; // llm_call steps are internal; tool activity comes via tool_result
          case "tool_result":
            return { ...x, steps: [...x.steps, { type: "tool", name: ev.name, status: ev.status }] };
          case "sources":
            return { ...x, citations: ev.citations };
          case "approval_required":
            return { ...x, approval: ev.approval, streaming: false };
          case "token":
            return { ...x, content: x.content + ev.text };
          case "done":
            return { ...x, meta: ev.meta, streaming: false };
          case "error":
            return { ...x, error: ev.message, streaming: false };
          default:
            return x;
        }
      }),
    );
  }

  async function runStream(id: string, gen: AsyncGenerator<AgentEvent>) {
    for await (const ev of gen) applyEvent(id, ev);
  }

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setInput("");

    const userId = crypto.randomUUID();
    const assistantId = crypto.randomUUID();
    setMessages((m) => [
      ...m,
      { id: userId, role: "user", content: q, steps: [] },
      { id: assistantId, role: "assistant", content: "", steps: [], streaming: true },
    ]);
    setActiveId(assistantId);
    setHighlighted(null);

    try {
      if (!conversationId.current) {
        conversationId.current = (await createConversation()).id;
      }
      await runStream(assistantId, streamAgent(conversationId.current, q));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Streaming failed";
      setMessages((m) => patch(m, assistantId, (x) => ({ ...x, error: message, streaming: false })));
    } finally {
      setBusy(false);
    }
  }

  async function decide(id: string, approval: ApprovalState, decision: "approve" | "reject", note?: string) {
    setBusy(true);
    setMessages((m) =>
      patch(m, id, (x) => ({ ...x, approval: { ...approval, deciding: true } })),
    );
    try {
      await decideApproval(approval.approval_id, decision, note);
      setMessages((m) =>
        patch(m, id, (x) => ({
          ...x,
          approval: { ...approval, deciding: false, decision: decision === "approve" ? "approved" : "rejected" },
          streaming: true,
        })),
      );
      await runStream(id, streamResume(approval.run_id));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Resume failed";
      setMessages((m) => patch(m, id, (x) => ({ ...x, error: message, streaming: false })));
    } finally {
      setBusy(false);
    }
  }

  const activeCitations = messages.find((m) => m.id === activeId)?.citations;

  return (
    <div className="flex flex-col gap-8 lg:flex-row">
      <div className="flex min-h-[70vh] flex-1 flex-col">
        <header className="mb-4">
          <h1 className="text-2xl font-semibold tracking-tight">Copilot</h1>
          <p className="mt-1 text-sm text-slate-500">
            The copilot searches the knowledge base, looks up orders, and can escalate to a human —
            with your approval before any action.
          </p>
        </header>

        <div className="flex-1 space-y-4">
          {messages.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <p className="text-sm font-medium text-slate-700">Try asking:</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    type="button"
                    onClick={() => send(ex)}
                    className="rounded-full border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition-colors hover:border-slate-400 hover:bg-slate-50"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-3",
                    m.role === "user" ? "bg-slate-900 text-sm text-white" : "border border-slate-200 bg-white",
                  )}
                >
                  {m.role === "user" ? (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.content}</p>
                  ) : (
                    <>
                      <StepTrail steps={m.steps} />
                      {m.content && (
                        <MessageContent
                          content={m.content}
                          onCite={(n) => {
                            setActiveId(m.id);
                            setHighlighted(n);
                          }}
                        />
                      )}
                      {m.streaming && !m.content && !m.approval && (
                        <div className="flex items-center gap-2 text-sm text-slate-400">
                          <Loader2 className="h-4 w-4 animate-spin" /> Working…
                        </div>
                      )}
                      {m.approval && (
                        <ApprovalCard
                          approval={m.approval}
                          onDecide={(decision, note) => decide(m.id, m.approval!, decision, note)}
                        />
                      )}
                      {m.error && <p className="mt-2 text-sm text-red-600">⚠ {m.error}</p>}
                      {m.meta && <AnswerMetaRow meta={m.meta} />}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="sticky bottom-0 mt-4 flex items-center gap-2 bg-slate-50 pt-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the copilot…"
            disabled={busy}
            className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-slate-500 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />}
            Send
          </button>
        </form>
      </div>

      <SourcesPanel citations={activeCitations} highlighted={highlighted} />
    </div>
  );
}
