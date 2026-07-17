"use client";

import { Loader2, SendHorizonal } from "lucide-react";
import { useRef, useState } from "react";

import { type AnswerMeta, type Citation, createConversation, streamAsk } from "@/lib/api/chat";
import { cn } from "@/lib/utils";

import { AnswerMetaRow } from "./answer-meta";
import { MessageContent } from "./message-content";
import { SourcesPanel } from "./sources-panel";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  meta?: AnswerMeta;
  streaming?: boolean;
  error?: string;
};

const EXAMPLES = [
  "How do I reset my password?",
  "How long do refunds take?",
  "Who handles escalations?",
];

function patch(messages: ChatMessage[], id: string, fn: (m: ChatMessage) => ChatMessage) {
  return messages.map((m) => (m.id === id ? fn(m) : m));
}

export function ChatView() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const conversationId = useRef<string | null>(null);

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setInput("");

    const userId = crypto.randomUUID();
    const assistantId = crypto.randomUUID();
    setMessages((m) => [
      ...m,
      { id: userId, role: "user", content: q },
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);
    setActiveMessageId(assistantId);
    setHighlighted(null);

    try {
      if (!conversationId.current) {
        conversationId.current = (await createConversation()).id;
      }
      for await (const ev of streamAsk(conversationId.current, q)) {
        if (ev.type === "sources") {
          setMessages((m) => patch(m, assistantId, (x) => ({ ...x, citations: ev.citations })));
        } else if (ev.type === "token") {
          setMessages((m) => patch(m, assistantId, (x) => ({ ...x, content: x.content + ev.text })));
        } else if (ev.type === "done") {
          setMessages((m) => patch(m, assistantId, (x) => ({ ...x, meta: ev.meta, streaming: false })));
        } else if (ev.type === "error") {
          setMessages((m) =>
            patch(m, assistantId, (x) => ({ ...x, error: ev.message, streaming: false })),
          );
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Streaming failed";
      setMessages((m) => patch(m, assistantId, (x) => ({ ...x, error: message, streaming: false })));
    } finally {
      setBusy(false);
    }
  }

  const activeCitations = messages.find((m) => m.id === activeMessageId)?.citations;

  return (
    <div className="flex flex-col gap-8 lg:flex-row">
      <div className="flex min-h-[70vh] flex-1 flex-col">
        <header className="mb-4">
          <h1 className="text-2xl font-semibold tracking-tight">Copilot</h1>
          <p className="mt-1 text-sm text-slate-500">
            Ask a question. Answers are grounded in your knowledge base with inline citations.
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
              <div
                key={m.id}
                className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-3",
                    m.role === "user"
                      ? "bg-slate-900 text-sm text-white"
                      : "border border-slate-200 bg-white",
                  )}
                >
                  {m.role === "user" ? (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.content}</p>
                  ) : (
                    <>
                      {m.content && (
                        <MessageContent
                          content={m.content}
                          onCite={(n) => {
                            setActiveMessageId(m.id);
                            setHighlighted(n);
                          }}
                        />
                      )}
                      {m.streaming && !m.content && (
                        <div className="flex items-center gap-2 text-sm text-slate-400">
                          <Loader2 className="h-4 w-4 animate-spin" /> Retrieving and thinking…
                        </div>
                      )}
                      {m.error && <p className="text-sm text-red-600">⚠ {m.error}</p>}
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
