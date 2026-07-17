"""RAG answer assembly: prompt construction, citation payloads, confidence.

Kept separate from the API layer so it's unit-testable without HTTP or a live LLM.
"""

import re

from app.core.llm.base import LLMMessage
from app.core.retrieval.retriever import RetrievedChunk

SYSTEM_PROMPT = (
    "You are a support-resolution assistant for an internal help desk. "
    "Answer the agent's question using ONLY the numbered sources provided. "
    "Cite every claim inline with the matching source number in square brackets, e.g. [1]. "
    "If the sources do not contain enough information to answer, say so plainly and "
    "recommend escalating to a human — do not guess. Be concise and specific."
)

_SNIPPET_CHARS = 240


def build_messages(question: str, retrieved: list[RetrievedChunk]) -> list[LLMMessage]:
    if retrieved:
        blocks = []
        for r in retrieved:
            locator = f" · {r.location}" if r.location else ""
            # Sources are untrusted data — delimited and labeled, never instructions.
            blocks.append(f"[{r.index}] ({r.filename}{locator})\n{r.text}")
        sources = "\n\n".join(blocks)
    else:
        sources = "(no relevant sources found)"

    user = f"Sources:\n{sources}\n\nQuestion: {question}"
    return [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content=user),
    ]


def citations_payload(retrieved: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "index": r.index,
            "document_id": str(r.document_id),
            "chunk_id": str(r.chunk_id),
            "filename": r.filename,
            "location": r.location,
            "snippet": r.text[:_SNIPPET_CHARS].strip(),
            "score": r.score,
        }
        for r in retrieved
    ]


def compute_confidence(retrieved: list[RetrievedChunk], answer: str) -> tuple[float, dict]:
    """Transparent heuristic, presented as such (not a calibrated probability).

    retrieval  = mean of the top-3 vector similarities
    coverage   = fraction of answer sentences that carry a [n] citation
    Weights are the architecture's 0.5 / 0.3 renormalized (self-score deferred).
    """
    sims = sorted((r.vector_similarity for r in retrieved), reverse=True)[:3]
    retrieval = sum(sims) / len(sims) if sims else 0.0

    sentences = [s for s in re.split(r"(?<=[.!?])\s+", answer.strip()) if s]
    cited = sum(1 for s in sentences if re.search(r"\[\d+\]", s))
    coverage = cited / len(sentences) if sentences else 0.0

    confidence = round(0.625 * retrieval + 0.375 * coverage, 3)
    parts = {
        "retrieval": round(retrieval, 3),
        "citation_coverage": round(coverage, 3),
        "self_score": None,  # deferred: would require a second LLM call
    }
    return confidence, parts
