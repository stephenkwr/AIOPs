from types import SimpleNamespace

from app.core.retrieval.retriever import _rrf


def _chunk(cid: str):
    return SimpleNamespace(id=cid)


def test_rrf_rewards_appearing_in_both_lists():
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
    # 'a' is mid-ranked in both lists; 'b' tops one list only; 'c' tops the other only.
    vector = [(b, 0.9), (a, 0.5)]
    keyword = [(c, 9.0), (a, 4.0)]
    ranked = _rrf([vector, keyword], top_k=3)
    assert ranked[0].id == "a"  # consensus wins over single-list leaders


def test_rrf_respects_top_k():
    chunks = [_chunk(str(i)) for i in range(5)]
    ranked = _rrf([[(c, 1.0) for c in chunks]], top_k=2)
    assert len(ranked) == 2
