"""Provider-agnostic LLM interface.

Two capabilities behind one set of types:
  * stream(...)              — token streaming for plain Q&A (Phase 2)
  * complete_with_tools(...) — one non-streamed turn that may return tool calls
                               (Phase 3 agent loop)

Call sites never import a vendor SDK; each adapter translates these types to/from
its provider's native format.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMMessage:
    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)  # assistant turns that call tools
    tool_call_id: str | None = None  # set on role="tool" result messages
    name: str | None = None  # tool name on role="tool" messages


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AssistantTurn:
    text: str
    tool_calls: list[ToolCall]
    usage: LLMUsage


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

    async def complete_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolSpec], *, max_tokens: int
    ) -> AssistantTurn: ...


async def collect(events: AsyncIterator[StreamEvent]) -> tuple[str, LLMUsage]:
    text = ""
    usage = LLMUsage()
    async for ev in events:
        if ev.type == "delta":
            text += ev.text
        elif ev.type == "done" and ev.usage is not None:
            usage = ev.usage
    return text, usage


# --- Serialization for durable agent state (run.agent_state JSONB) -----------


def messages_to_dicts(messages: list[LLMMessage]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        d: dict = {"role": m.role, "content": m.content}
        if m.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in m.tool_calls
            ]
        if m.tool_call_id is not None:
            d["tool_call_id"] = m.tool_call_id
        if m.name is not None:
            d["name"] = m.name
        out.append(d)
    return out


def messages_from_dicts(data: list[dict]) -> list[LLMMessage]:
    messages: list[LLMMessage] = []
    for d in data:
        messages.append(
            LLMMessage(
                role=d["role"],
                content=d.get("content", ""),
                tool_calls=[
                    ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                    for tc in d.get("tool_calls", [])
                ],
                tool_call_id=d.get("tool_call_id"),
                name=d.get("name"),
            )
        )
    return messages
