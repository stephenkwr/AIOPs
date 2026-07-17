"""Offline LLM for hermetic tests and no-key local runs.

For plain chat it streams a deterministic cited answer. For the agent loop it
follows a fixed policy so tests can drive every branch (search → optionally
look up an order / escalate → final answer).
"""

from collections.abc import AsyncIterator

from app.core.llm.base import (
    AssistantTurn,
    LLMMessage,
    LLMUsage,
    StreamEvent,
    ToolCall,
    ToolSpec,
)


class FakeLLMClient:
    model = "fake-llm"

    async def stream(
        self, messages: list[LLMMessage], *, max_tokens: int
    ) -> AsyncIterator[StreamEvent]:
        answer = "Based on the knowledge base, here is the answer to your question. [1]"
        words = answer.split(" ")
        for word in words:
            yield StreamEvent(type="delta", text=word + " ")
        yield StreamEvent(type="done", usage=LLMUsage(input_tokens=42, output_tokens=len(words)))

    async def complete_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolSpec], *, max_tokens: int
    ) -> AssistantTurn:
        tool_names = {t.name for t in tools}
        called = {tc.name for m in messages if m.role == "assistant" for tc in m.tool_calls}
        user_text = next((m.content for m in messages if m.role == "user"), "").lower()
        usage = LLMUsage(input_tokens=50, output_tokens=10)

        # 1. Always ground in the knowledge base first.
        if "search_knowledge_base" in tool_names and "search_knowledge_base" not in called:
            return AssistantTurn(
                text="",
                tool_calls=[
                    ToolCall(id="kb1", name="search_knowledge_base", arguments={"query": user_text})
                ],
                usage=usage,
            )
        # 2. If asked to look up an order.
        if "order" in user_text and "lookup_order" in tool_names and "lookup_order" not in called:
            return AssistantTurn(
                text="",
                tool_calls=[
                    ToolCall(id="ord1", name="lookup_order", arguments={"order_number": "1042"})
                ],
                usage=usage,
            )
        # 3. If asked to escalate (side-effect tool → approval gate).
        if (
            "escalat" in user_text
            and "create_escalation" in tool_names
            and "create_escalation" not in called
        ):
            return AssistantTurn(
                text="",
                tool_calls=[
                    ToolCall(
                        id="esc1",
                        name="create_escalation",
                        arguments={"summary": user_text[:80] or "escalation", "priority": "high"},
                    )
                ],
                usage=usage,
            )
        # 4. Final answer.
        return AssistantTurn(
            text="Based on the knowledge base, here is the answer to your question. [1]",
            tool_calls=[],
            usage=usage,
        )
