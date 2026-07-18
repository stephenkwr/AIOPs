"""Hybrid retrieval: pgvector cosine + Postgres full-text, fused with RRF.

Vector search catches paraphrase/semantic matches; keyword search catches exact
identifiers (SKUs, error codes, order numbers) that embeddings often miss.
Reciprocal Rank Fusion combines them with no score-scale tuning.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.embedder import Embedder, get_embedder
from app.models import Chunk

RRF_K = 60


@dataclass
class RetrievedChunk:
    index: int  # 1-based citation number
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    ord: int
    text: str
    score: float  # fused score (RRF) or vector similarity in vector-only mode
    vector_similarity: float  # cosine similarity, for the confidence heuristic
    location: str | None  # human-readable source locator (page / rows / heading)


def _location(meta: dict) -> str | None:
    if meta.get("page") is not None:
        return f"p.{meta['page']}"
    if meta.get("rows"):
        return f"rows {meta['rows']}"
    if meta.get("heading"):
        return str(meta["heading"])
    return None


async def _vector_search(
    session: AsyncSession, workspace_id: uuid.UUID, qvec: list[float], limit: int
) -> list[tuple[Chunk, float]]:
    distance = Chunk.embedding.cosine_distance(qvec).label("distance")
    rows = (
        await session.execute(
            select(Chunk, distance)
            .where(Chunk.workspace_id == workspace_id)
            .order_by(distance)
            .limit(limit)
        )
    ).all()
    # cosine distance -> similarity
    return [(chunk, 1.0 - float(dist)) for chunk, dist in rows]


async def _keyword_search(
    session: AsyncSession, workspace_id: uuid.UUID, query: str, limit: int
) -> list[tuple[Chunk, float]]:
    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank_cd(Chunk.tsv, tsquery).label("rank")
    rows = (
        await session.execute(
            select(Chunk, rank)
            .where(Chunk.workspace_id == workspace_id, Chunk.tsv.op("@@")(tsquery))
            .order_by(rank.desc())
            .limit(limit)
        )
    ).all()
    return [(chunk, float(r)) for chunk, r in rows]


def _rrf(ranked_lists: list[list[tuple[Chunk, float]]], top_k: int) -> list[Chunk]:
    scores: dict[uuid.UUID, float] = {}
    seen: dict[uuid.UUID, Chunk] = {}
    for ranked in ranked_lists:
        for rank, (chunk, _score) in enumerate(ranked):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (RRF_K + rank + 1)
            seen[chunk.id] = chunk
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [seen[cid] for cid, _ in ordered]


async def retrieve(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    query: str,
    *,
    mode: str = "hybrid",
    k: int = 8,
    candidates: int = 20,
    embedder: Embedder | None = None,
) -> list[RetrievedChunk]:
    # keyword mode is the lexical-only baseline (the eval "before"): no embedding
    # call, no vector ranking — pure Postgres full-text search.
    if mode == "keyword":
        keyword_hits = await _keyword_search(session, workspace_id, query, candidates)
        chosen = [chunk for chunk, _ in keyword_hits[:k]]
        scores = {chunk.id: score for chunk, score in keyword_hits}
        vector_sim: dict[uuid.UUID, float] = {}
    else:
        embedder = embedder or get_embedder()
        qvec = await embedder.embed_query(query)
        vector_hits = await _vector_search(session, workspace_id, qvec, candidates)
        vector_sim = {chunk.id: sim for chunk, sim in vector_hits}

        if mode == "vector":
            chosen = [chunk for chunk, _ in vector_hits[:k]]
            scores = {c.id: vector_sim.get(c.id, 0.0) for c in chosen}
        else:  # hybrid
            keyword_hits = await _keyword_search(session, workspace_id, query, candidates)
            chosen = _rrf([vector_hits, keyword_hits], top_k=k)
            # Display score = RRF contribution, for ordering transparency.
            scores = {}
            for ranked in (vector_hits, keyword_hits):
                for rank, (chunk, _s) in enumerate(ranked):
                    scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (RRF_K + rank + 1)

    results: list[RetrievedChunk] = []
    for i, chunk in enumerate(chosen):
        results.append(
            RetrievedChunk(
                index=i + 1,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                filename=str(chunk.meta.get("filename", "(unknown)")),
                ord=chunk.ord,
                text=chunk.text,
                score=round(scores.get(chunk.id, 0.0), 6),
                vector_similarity=round(max(0.0, vector_sim.get(chunk.id, 0.0)), 4),
                location=_location(chunk.meta),
            )
        )
    return results
