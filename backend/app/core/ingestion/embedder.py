"""Embedding providers behind one interface.

  * GeminiEmbedder  — real embeddings via gemini-embedding-001 at 768 dims.
  * HashingEmbedder — offline feature-hashing (the "trick"): no API key, no
    network. Deterministic and lexically meaningful (texts sharing words get
    similar vectors), so local dev and CI get working retrieval for free.

get_embedder() picks based on config: EMBED_PROVIDER=auto uses Gemini when a key
is present, otherwise the hashing embedder.
"""

import asyncio
import hashlib
import math
import re
from typing import Protocol

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

_TOKEN = re.compile(r"[a-z0-9]+")
_GEMINI_BATCH = 100


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class Embedder(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Signed feature hashing → unit vectors. Deterministic, offline."""

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN.findall(text.lower()):
            h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")
            idx = h % self.dim
            sign = 1.0 if (h >> 17) & 1 else -1.0
            vec[idx] += sign
        if not any(vec):
            vec[0] = 1e-6  # avoid a zero vector for empty/tokenless text
        return _l2_normalize(vec)


class GeminiEmbedder:
    def __init__(self, api_key: str, model: str, dim: int = 768) -> None:
        from google import genai  # lazy: only import the SDK when actually used

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), _GEMINI_BATCH):
            out.extend(await self._embed_batch(texts[start : start + _GEMINI_BATCH]))
        return out

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        from google.genai import types

        resp = await asyncio.to_thread(
            self._client.models.embed_content,
            model=self.model,
            contents=batch,
            config=types.EmbedContentConfig(
                output_dimensionality=self.dim,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        # Truncated (<3072-dim) embeddings aren't returned normalized — do it here.
        return [_l2_normalize(list(e.values)) for e in resp.embeddings]


def get_embedder() -> Embedder:
    provider = settings.embed_provider
    if provider == "fake":
        return HashingEmbedder(settings.embed_dim)
    if provider == "gemini" or (provider == "auto" and settings.gemini_api_key):
        if not settings.gemini_api_key:
            raise RuntimeError("EMBED_PROVIDER=gemini but GEMINI_API_KEY is not set")
        return GeminiEmbedder(settings.gemini_api_key, settings.embed_model, settings.embed_dim)
    return HashingEmbedder(settings.embed_dim)
