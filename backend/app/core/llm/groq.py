"""Groq chat via the async Groq client (OpenAI-style API)."""

from collections.abc import AsyncIterator

from app.core.llm.base import LLMMessage, LLMUsage, StreamEvent


class GroqClient:
    def __init__(self, api_key: str, model: str) -> None:
        from groq import AsyncGroq

        self._client = AsyncGroq(api_key=api_key)
        self.model = model

    async def stream(
        self, messages: list[LLMMessage], *, max_tokens: int
    ) -> AsyncIterator[StreamEvent]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens,
            stream=True,
            # include_usage goes via extra_body: this SDK version doesn't expose
            # stream_options as a named parameter.
            extra_body={"stream_options": {"include_usage": True}},
        )
        usage = LLMUsage()
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield StreamEvent(type="delta", text=chunk.choices[0].delta.content)
            if getattr(chunk, "usage", None):
                usage = LLMUsage(
                    input_tokens=chunk.usage.prompt_tokens or 0,
                    output_tokens=chunk.usage.completion_tokens or 0,
                )
        yield StreamEvent(type="done", usage=usage)
