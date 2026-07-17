"""Groq chat via the async Groq client (OpenAI-style API)."""

import json
from collections.abc import AsyncIterator

from app.core.llm.base import (
    AssistantTurn,
    LLMMessage,
    LLMUsage,
    StreamEvent,
    ToolCall,
    ToolSpec,
)


def _to_openai(messages: list[LLMMessage]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
        elif m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in m.tool_calls
                    ],
                }
            )
        else:
            out.append({"role": m.role, "content": m.content})
    return out


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
            messages=_to_openai(messages),
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

    async def complete_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolSpec], *, max_tokens: int
    ) -> AssistantTurn:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=_to_openai(messages),
            max_tokens=max_tokens,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ],
            tool_choice="auto",
        )
        message = resp.choices[0].message
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in (message.tool_calls or [])
        ]
        usage = LLMUsage(
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )
        return AssistantTurn(text=message.content or "", tool_calls=tool_calls, usage=usage)
