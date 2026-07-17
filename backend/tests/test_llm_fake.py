from app.core.llm.base import LLMMessage, collect
from app.core.llm.fake import FakeLLMClient


async def test_fake_llm_streams_and_reports_usage():
    client = FakeLLMClient()
    text, usage = await collect(
        client.stream([LLMMessage(role="user", content="hi")], max_tokens=64)
    )
    assert "[1]" in text
    assert usage.output_tokens > 0
