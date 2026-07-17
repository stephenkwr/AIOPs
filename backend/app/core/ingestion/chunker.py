"""Split parsed documents into embeddable chunks.

Two strategies:
  * "structure" — respects section boundaries (pages/rows), packs sentences up to a
    token budget with overlap so context isn't cut mid-thought. The default.
  * "naive"     — fixed-size character windows, no structure, no overlap. Kept
    deliberately as the eval "before" baseline (Phase 5).

Token counts are estimated (~4 chars/token). Exact counts aren't needed for sizing,
and this avoids shipping a tokenizer for every provider.
"""

import re
from dataclasses import dataclass

from app.core.ingestion.parsers import ParsedDoc

_PARAGRAPH = re.compile(r"\n{2,}")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class TextChunk:
    ord: int
    text: str
    token_count: int
    meta: dict


def chunk_document(
    parsed: ParsedDoc,
    *,
    strategy: str = "structure",
    target_tokens: int = 800,
    overlap_ratio: float = 0.15,
    base_meta: dict | None = None,
) -> list[TextChunk]:
    base_meta = base_meta or {}
    if strategy == "naive":
        pieces = _naive(parsed, target_tokens)
        metas = [dict(base_meta, strategy="naive") for _ in pieces]
    else:
        pieces, metas = _structure(parsed, target_tokens, overlap_ratio, base_meta)

    return [
        TextChunk(ord=i, text=text, token_count=estimate_tokens(text), meta=meta)
        for i, (text, meta) in enumerate(zip(pieces, metas, strict=True))
    ]


def _split_units(text: str) -> list[str]:
    """Break text into sentence-ish units, hard-splitting any that are too long."""
    units: list[str] = []
    for para in _PARAGRAPH.split(text.strip()):
        for sent in _SENTENCE.split(para.strip()):
            sent = sent.strip()
            if sent:
                units.append(sent)
    return units


def _hard_split(unit: str, target_tokens: int) -> list[str]:
    """Character-slice a single oversized unit so no chunk wildly exceeds the budget."""
    max_chars = target_tokens * 4
    if len(unit) <= max_chars:
        return [unit]
    return [unit[i : i + max_chars] for i in range(0, len(unit), max_chars)]


def _pack(units: list[str], target_tokens: int, overlap_ratio: float) -> list[str]:
    overlap_tokens = int(target_tokens * overlap_ratio)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for unit in units:
        for part in _hard_split(unit, target_tokens):
            part_tokens = estimate_tokens(part)
            if current and current_tokens + part_tokens > target_tokens:
                chunks.append(" ".join(current))
                # Carry a tail of the previous chunk forward as overlap.
                tail: list[str] = []
                tail_tokens = 0
                for prev in reversed(current):
                    t = estimate_tokens(prev)
                    if tail_tokens + t > overlap_tokens:
                        break
                    tail.insert(0, prev)
                    tail_tokens += t
                current = tail
                current_tokens = tail_tokens
            current.append(part)
            current_tokens += part_tokens

    if current:
        chunks.append(" ".join(current))
    return chunks


def _structure(
    parsed: ParsedDoc, target_tokens: int, overlap_ratio: float, base_meta: dict
) -> tuple[list[str], list[dict]]:
    texts: list[str] = []
    metas: list[dict] = []
    for section in parsed.sections:
        for piece in _pack(_split_units(section.text), target_tokens, overlap_ratio):
            texts.append(piece)
            metas.append(dict(base_meta, **section.meta, strategy="structure"))
    return texts, metas


def _naive(parsed: ParsedDoc, target_tokens: int) -> list[str]:
    full = "\n".join(s.text for s in parsed.sections).strip()
    if not full:
        return []
    window = target_tokens * 4
    return [full[i : i + window] for i in range(0, len(full), window)]
