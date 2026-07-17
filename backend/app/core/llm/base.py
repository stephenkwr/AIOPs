"""Provider-agnostic LLM interface.

Every provider (Gemini, Groq, Anthropic, the test fake) implements the same
`stream(...)` method yielding text deltas and a final usage record. Call sites
never import a vendor SDK — they depend only on these types. Swapping providers
is a config change, which is exactly what a commercial "LLM gateway" sells.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass
class LLMMessage:
    role: Role
    content: str


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class StreamEvent:
    type: Literal["delta", "done"]
    text: str = ""
    usage: LLMUsage | None = None


@runtime_checkable
class LLMClient(Protocol):
    model: str

    def stream(
        self, messages: list[LLMMessage], *, max_tokens: int
    ) -> AsyncIterator[StreamEvent]: ...


async def collect(events: AsyncIterator[StreamEvent]) -> tuple[str, LLMUsage]:
    """Drain a stream into the full text and final usage (for non-streaming callers/tests)."""
    text = ""
    usage = LLMUsage()
    async for ev in events:
        if ev.type == "delta":
            text += ev.text
        elif ev.type == "done" and ev.usage is not None:
            usage = ev.usage
    return text, usage
