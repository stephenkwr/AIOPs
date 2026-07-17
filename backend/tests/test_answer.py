import uuid

from app.core.answer import build_messages, citations_payload, compute_confidence
from app.core.retrieval.retriever import RetrievedChunk


def _rc(index: int, sim: float) -> RetrievedChunk:
    return RetrievedChunk(
        index=index,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="faq.csv",
        ord=0,
        text=f"Source text number {index} about resetting passwords.",
        score=0.1,
        vector_similarity=sim,
        location="rows 1-10",
    )


def test_build_messages_includes_numbered_sources_and_question():
    msgs = build_messages("How do I reset my password?", [_rc(1, 0.8), _rc(2, 0.6)])
    assert msgs[0].role == "system"
    user = msgs[1].content
    assert "[1]" in user and "[2]" in user
    assert "How do I reset my password?" in user
    assert "faq.csv" in user


def test_build_messages_handles_no_sources():
    msgs = build_messages("anything", [])
    assert "no relevant sources" in msgs[1].content.lower()


def test_citations_payload_shape():
    payload = citations_payload([_rc(1, 0.8)])
    assert payload[0]["index"] == 1
    assert payload[0]["filename"] == "faq.csv"
    assert "snippet" in payload[0]


def test_confidence_rewards_citation_coverage():
    retrieved = [_rc(1, 0.9), _rc(2, 0.8), _rc(3, 0.7)]
    cited = "The answer is here [1]. More detail [2]."
    uncited = "The answer is here. More detail."
    c_cited, parts_cited = compute_confidence(retrieved, cited)
    c_uncited, _ = compute_confidence(retrieved, uncited)
    assert c_cited > c_uncited
    assert parts_cited["citation_coverage"] == 1.0
    assert parts_cited["self_score"] is None
