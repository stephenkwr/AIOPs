"""Offline LLM for hermetic tests and no-key local runs.

Produces a deterministic, source-citing answer so the chat pipeline can be tested
end-to-end without a provider key.
"""

from collections.abc import AsyncIterator

from app.core.llm.base import LLMMessage, LLMUsage, StreamEvent


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
