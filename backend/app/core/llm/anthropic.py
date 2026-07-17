"""Claude chat via the official Anthropic SDK.

Dormant unless ANTHROPIC_API_KEY is set and LLM_PROVIDER=anthropic — the premium
swap-in. Uses the official SDK's streaming helper (never an OpenAI-compat shim).
"""

from collections.abc import AsyncIterator

from app.core.llm.base import AssistantTurn, LLMMessage, LLMUsage, StreamEvent, ToolSpec


class AnthropicClient:
    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def stream(
        self, messages: list[LLMMessage], *, max_tokens: int
    ) -> AsyncIterator[StreamEvent]:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        conversation = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        kwargs: dict = {"model": self.model, "max_tokens": max_tokens, "messages": conversation}
        if system:
            kwargs["system"] = system

        usage = LLMUsage()
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield StreamEvent(type="delta", text=text)
            final = await stream.get_final_message()
            usage = LLMUsage(
                input_tokens=final.usage.input_tokens,
                output_tokens=final.usage.output_tokens,
            )
        yield StreamEvent(type="done", usage=usage)

    async def complete_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolSpec], *, max_tokens: int
    ) -> AssistantTurn:
        # Deferred: the streaming Q&A path works, but tool-calling isn't wired for
        # Claude yet (no key available to verify against). The agent loop runs on
        # Gemini/Groq. Implement with the SDK's tool_use blocks when adding Claude.
        raise NotImplementedError("Anthropic tool-calling is not yet implemented")
