"""Gemini chat via the async google-genai client (streaming + function calling)."""

from collections.abc import AsyncIterator

from app.core.llm.base import (
    AssistantTurn,
    LLMMessage,
    LLMUsage,
    StreamEvent,
    ToolCall,
    ToolSpec,
)


def _to_gemini_contents(messages: list[LLMMessage]) -> tuple[str, list[dict]]:
    """Split into (system_instruction, contents). Roles: user / model / function."""
    system_parts: list[str] = []
    contents: list[dict] = []
    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        elif m.role == "tool":
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "function_response": {
                                "name": m.name or "tool",
                                "response": {"result": m.content},
                            }
                        }
                    ],
                }
            )
        elif m.role == "assistant" and m.tool_calls:
            contents.append(
                {
                    "role": "model",
                    "parts": [
                        {"function_call": {"name": tc.name, "args": tc.arguments}}
                        for tc in m.tool_calls
                    ],
                }
            )
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

        system, contents = _to_gemini_contents(messages)
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens, system_instruction=system or None
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

    async def complete_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolSpec], *, max_tokens: int
    ) -> AssistantTurn:
        from google.genai import types

        system, contents = _to_gemini_contents(messages)
        declarations = [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in tools
        ]
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            system_instruction=system or None,
            tools=[types.Tool(function_declarations=declarations)],
        )
        resp = await self._client.aio.models.generate_content(
            model=self.model, contents=contents, config=config
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for i, fc in enumerate(resp.function_calls or []):
            tool_calls.append(ToolCall(id=f"call_{i}", name=fc.name, arguments=dict(fc.args or {})))
        if not tool_calls and resp.text:
            text_parts.append(resp.text)

        um = resp.usage_metadata
        usage = LLMUsage(
            input_tokens=(um.prompt_token_count or 0) if um else 0,
            output_tokens=(um.candidates_token_count or 0) if um else 0,
        )
        return AssistantTurn(text="".join(text_parts), tool_calls=tool_calls, usage=usage)
