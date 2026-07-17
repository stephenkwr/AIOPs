"""Gemini chat via the async google-genai client."""

from collections.abc import AsyncIterator

from app.core.llm.base import LLMMessage, LLMUsage, StreamEvent


def _to_gemini(messages: list[LLMMessage]) -> tuple[str, list[dict]]:
    """Split into (system_instruction, contents). Gemini uses roles user/model."""
    system_parts: list[str] = []
    contents: list[dict] = []
    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        else:
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})
    return "\n\n".join(system_parts), contents


class GeminiClient:
    def __init__(self, api_key: str, model: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model

    async def stream(
        self, messages: list[LLMMessage], *, max_tokens: int
    ) -> AsyncIterator[StreamEvent]:
        from google.genai import types

        system, contents = _to_gemini(messages)
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            system_instruction=system or None,
        )
        usage = LLMUsage()
        stream = await self._client.aio.models.generate_content_stream(
            model=self.model, contents=contents, config=config
        )
        async for chunk in stream:
            if chunk.text:
                yield StreamEvent(type="delta", text=chunk.text)
            if chunk.usage_metadata:
                usage = LLMUsage(
                    input_tokens=chunk.usage_metadata.prompt_token_count or 0,
                    output_tokens=chunk.usage_metadata.candidates_token_count or 0,
                )
        yield StreamEvent(type="done", usage=usage)
