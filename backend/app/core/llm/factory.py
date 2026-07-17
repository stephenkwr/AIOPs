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
