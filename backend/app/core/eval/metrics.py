"""Pure scoring functions for the eval harness — no I/O, unit-testable.

Retrieval is scored at the document level: each answerable question is authored
from exactly one source doc, so the gold label is that filename. hit@k asks
whether the gold doc appears in the top-k retrieved; MRR rewards ranking it high.
"""

import re

# --- retrieval -------------------------------------------------------------


def retrieval_metrics(
    gold_doc: str | None, retrieved: list[str], k: int
) -> tuple[bool, int | None, float]:
    """Return (hit, rank, reciprocal_rank) for one question.

    hit  = gold doc is within the top-k retrieved filenames
    rank = 1-based position of the first gold hit (None if absent)
    rr   = 1/rank, or 0.0 if the gold doc was never retrieved
    """
    if not gold_doc:
        return False, None, 0.0
    top = retrieved[:k]
    for i, fn in enumerate(top):
        if fn == gold_doc:
            return True, i + 1, 1.0 / (i + 1)
    return False, None, 0.0


# --- refusal detection (heuristic) -----------------------------------------

_REFUSAL_MARKERS = (
    "don't have",
    "do not have",
    "couldn't find",
    "could not find",
    "no information",
    "not able to",
    "unable to",
    "can't help",
    "cannot help",
    "can't assist",
    "escalat",
    "contact support",
    "human agent",
    "not covered",
    "don't know",
    "do not know",
    "i'm not sure",
    "no relevant",
    "outside",
)


def looks_like_refusal(answer: str) -> bool:
    low = answer.lower()
    return any(marker in low for marker in _REFUSAL_MARKERS)


# --- token overlap (heuristic grading) -------------------------------------

_STOP = frozenset(
    "the a an and or of to in for on at is are was were be by with your you it this that "
    "how do does can i my we our will if from as at".split()
)


def _content_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 2}


def token_recall(candidate: str, reference: str) -> float:
    """Fraction of the reference's content tokens that appear in the candidate."""
    ref = _content_tokens(reference)
    if not ref:
        return 0.0
    cand = _content_tokens(candidate)
    return round(len(ref & cand) / len(ref), 4)
