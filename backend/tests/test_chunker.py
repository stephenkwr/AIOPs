from app.core.ingestion.chunker import chunk_document, estimate_tokens
from app.core.ingestion.parsers import ParsedDoc, Section


def _long_doc(sentences: int = 200) -> ParsedDoc:
    text = " ".join(f"This is sentence number {i} about widgets." for i in range(sentences))
    return ParsedDoc(sections=[Section(text=text, meta={"page": 1})])


def test_structure_chunks_respect_budget_and_carry_meta():
    parsed = _long_doc()
    chunks = chunk_document(parsed, strategy="structure", target_tokens=100, overlap_ratio=0.15)
    assert len(chunks) > 1
    assert [c.ord for c in chunks] == list(range(len(chunks)))
    for c in chunks:
        # allow a little slack for the trailing unit that tips over the budget
        assert c.token_count <= 160
        assert c.meta["page"] == 1
        assert c.meta["strategy"] == "structure"


def test_structure_has_overlap_between_consecutive_chunks():
    parsed = _long_doc()
    chunks = chunk_document(parsed, strategy="structure", target_tokens=100, overlap_ratio=0.3)
    first_tail = chunks[0].text.split()[-4:]
    # some of the tail of chunk 0 should reappear at the head of chunk 1
    assert any(word in chunks[1].text.split()[:20] for word in first_tail)


def test_naive_ignores_structure():
    parsed = _long_doc()
    chunks = chunk_document(parsed, strategy="naive", target_tokens=100)
    assert len(chunks) > 1
    assert all(c.meta["strategy"] == "naive" for c in chunks)


def test_empty_document_yields_no_chunks():
    assert chunk_document(ParsedDoc(sections=[]), strategy="structure") == []


def test_estimate_tokens_is_positive():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 400) == 100
