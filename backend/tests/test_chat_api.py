import asyncio
import json

from httpx import AsyncClient


async def _upload_and_wait(client: AsyncClient, name: str, content: bytes) -> None:
    r = await client.post("/api/v1/documents", files={"file": (name, content, "text/plain")})
    doc_id = r.json()["id"]
    for _ in range(50):
        body = (await client.get(f"/api/v1/documents/{doc_id}")).json()
        if body["status"] in ("ready", "failed"):
            return
        await asyncio.sleep(0.1)


async def _collect_sse(resp) -> list[tuple[str, dict | None]]:
    events: list[tuple[str, dict | None]] = []
    event_name: str | None = None
    data: str | None = None
    async for line in resp.aiter_lines():
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].strip()
        elif line == "":
            if event_name is not None:
                events.append((event_name, json.loads(data) if data else None))
            event_name, data = None, None
    return events


async def test_ask_streams_cited_answer(client: AsyncClient, db_ready: None) -> None:
    await _upload_and_wait(client, "kb.txt", b"Refunds are processed within five business days.")
    conv = (await client.post("/api/v1/conversations", json={})).json()

    async with client.stream(
        "POST",
        f"/api/v1/conversations/{conv['id']}/ask",
        json={"question": "How long do refunds take?"},
    ) as resp:
        assert resp.status_code == 200
        events = await _collect_sse(resp)

    kinds = [name for name, _ in events]
    assert kinds[0] == "sources"
    assert "token" in kinds
    assert kinds[-1] == "done"

    done_payload = next(payload for name, payload in events if name == "done")
    run = (await client.get(f"/api/v1/runs/{done_payload['run_id']}")).json()
    assert run["status"] == "completed"
    assert "[1]" in run["answer"]
    assert run["tokens_out"] > 0
    assert isinstance(run["citations"], list)
    assert run["confidence"] is not None


async def test_conversation_detail_records_turns(client: AsyncClient, db_ready: None) -> None:
    conv = (await client.post("/api/v1/conversations", json={"title": "t"})).json()
    async with client.stream(
        "POST", f"/api/v1/conversations/{conv['id']}/ask", json={"question": "hi there"}
    ) as resp:
        async for _ in resp.aiter_lines():
            pass

    detail = (await client.get(f"/api/v1/conversations/{conv['id']}")).json()
    roles = [m["role"] for m in detail["messages"]]
    assert "user" in roles
    assert "assistant" in roles
