"""Ordered provider fallback (e.g. Gemini → Groq).

If a provider fails *before* producing any output (429/503/auth), transparently
try the next one. A failure *after* streaming has begun can't be recovered
cleanly, so it propagates. `last_model` records which provider actually served
the response, so the run trace shows the truth.
"""

from collections.abc import AsyncIterator

from app.core.llm.base import LLMClient, StreamEvent


class FallbackLLMClient:
    def __init__(self, clients: list[LLMClient]) -> None:
        if not clients:
            raise ValueError("FallbackLLMClient needs at least one client")
        self._clients = clients
        self.model = clients[0].model
        self.last_model = clients[0].model

    async def stream(self, messages: list, *, max_tokens: int) -> AsyncIterator[StreamEvent]:
        last_exc: Exception | None = None
        for client in self._clients:
            produced = False
            self.last_model = client.model
            try:
                async for ev in client.stream(messages, max_tokens=max_tokens):
                    produced = True
                    yield ev
                return
            except Exception as exc:  # noqa: BLE001 — try the next provider
                last_exc = exc
                if produced:
                    raise  # mid-stream failure: can't fail over without duplicating output
                continue
        if last_exc is not None:
            raise last_exc
