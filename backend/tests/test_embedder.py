import math

from app.core.ingestion.embedder import HashingEmbedder


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_hashing_embedder_dim_and_normalized():
    emb = HashingEmbedder(dim=768)
    [v] = await emb.embed(["hello world"])
    assert len(v) == 768
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-6)


async def test_hashing_embedder_deterministic():
    emb = HashingEmbedder(dim=768)
    a1 = (await emb.embed(["the quick brown fox"]))[0]
    a2 = (await emb.embed(["the quick brown fox"]))[0]
    assert a1 == a2


async def test_hashing_embedder_lexical_similarity():
    emb = HashingEmbedder(dim=768)
    base, similar, different = await emb.embed(
        [
            "reset my password on the account page",
            "how do I reset the password for my account",
            "the weather in tokyo is sunny today",
        ]
    )
    assert _cosine(base, similar) > _cosine(base, different)


async def test_hashing_embedder_handles_empty_text():
    emb = HashingEmbedder(dim=768)
    [v] = await emb.embed([""])
    assert len(v) == 768
    assert any(x != 0.0 for x in v)
