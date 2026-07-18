"""Select the LLM client from configuration.

auto  -> a fallback chain of every configured provider (Gemini → Groq → Anthropic),
         falling back to the offline fake if no key is set.
gemini/groq/anthropic -> that provider only (errors if its key is missing).
fake  -> the offline deterministic client.
"""

from app.config import settings
from app.core.llm.base import LLMClient
from app.core.llm.fake import FakeLLMClient


def _gemini() -> LLMClient:
    from app.core.llm.gemini import GeminiClient

    return GeminiClient(settings.gemini_api_key, settings.agent_model)


def _groq() -> LLMClient:
    from app.core.llm.groq import GroqClient

    return GroqClient(settings.groq_api_key, settings.groq_model)


def _anthropic() -> LLMClient:
    from app.core.llm.anthropic import AnthropicClient

    return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model)


def get_answer_client() -> LLMClient:
    provider = settings.llm_provider

    if provider == "fake":
        return FakeLLMClient()
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY is not set")
        return _gemini()
    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("LLM_PROVIDER=groq but GROQ_API_KEY is not set")
        return _groq()
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        return _anthropic()

    # auto: chain whatever is configured.
    chain: list[LLMClient] = []
    if settings.gemini_api_key:
        chain.append(_gemini())
    if settings.groq_api_key:
        chain.append(_groq())
    if settings.anthropic_api_key:
        chain.append(_anthropic())

    if not chain:
        return FakeLLMClient()
    if len(chain) == 1:
        return chain[0]

    from app.core.llm.fallback import FallbackLLMClient

    return FallbackLLMClient(chain)


def _provider_of(model: str | None) -> str | None:
    if not model:
        return None
    m = model.lower()
    if "gemini" in m:
        return "gemini"
    if "llama" in m or "groq" in m:
        return "groq"
    if "claude" in m:
        return "anthropic"
    return None


def get_judge_client(avoid_model: str | None = None) -> LLMClient | None:
    """A judge client for LLM-as-judge grading.

    Prefers a provider DIFFERENT from the one that produced the answer (avoids a
    model grading its own output — self-preference bias). Returns None when only
    the offline fake is available, so the caller falls back to heuristic grading.
    """
    if settings.llm_provider == "fake":
        return None

    avoid = _provider_of(avoid_model)
    # Groq first (reliable free tier), then Anthropic, then Gemini.
    order: list[tuple[str, object]] = []
    if settings.groq_api_key:
        order.append(("groq", _groq))
    if settings.anthropic_api_key:
        order.append(("anthropic", _anthropic))
    if settings.gemini_api_key:
        order.append(("gemini", _gemini))
    if not order:
        return None

    preferred = [c for c in order if c[0] != avoid] or order
    return preferred[0][1]()  # type: ignore[operator]
