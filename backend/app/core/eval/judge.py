"""Grade a generated answer: groundedness + correctness + refusal.

Two implementations behind one Grade result:
  * heuristic_grade — deterministic token-overlap scoring; used offline/CI.
  * llm_grade       — LLM-as-judge via a cross-provider client (Groq judging a
                      Gemini answer, etc.), forced through a structured grade tool.
"""

import json
from dataclasses import dataclass

from app.core.eval.dataset import DatasetItem
from app.core.eval.metrics import looks_like_refusal, token_recall
from app.core.llm.base import LLMClient, LLMMessage, ToolSpec
from app.core.retrieval.retriever import RetrievedChunk


@dataclass
class Grade:
    groundedness: float  # 0..1 — is the answer supported by the retrieved context?
    correctness: float  # 0..1 — does it match the reference answer?
    refused: bool  # did the answer decline / defer to a human?
    reasoning: str


_GRADE_TOOL = ToolSpec(
    name="submit_grade",
    description="Submit your evaluation of the assistant's answer.",
    parameters={
        "type": "object",
        "properties": {
            "groundedness": {
                "type": "number",
                "description": (
                    "0.0-1.0: is every claim in the answer supported by the provided "
                    "context? 1.0 = fully grounded, 0.0 = fabricated."
                ),
            },
            "correctness": {
                "type": "number",
                "description": ("0.0-1.0: does the answer match the reference answer's facts?"),
            },
            "refused": {
                "type": "boolean",
                "description": (
                    "true if the answer declined, said it lacked information, or "
                    "deferred to a human."
                ),
            },
            "reasoning": {"type": "string", "description": "One sentence justifying the scores."},
        },
        "required": ["groundedness", "correctness", "refused", "reasoning"],
    },
)

_JUDGE_SYSTEM = (
    "You are a strict evaluator for a customer-support RAG assistant. Judge the "
    "assistant's answer against the retrieved context and the reference answer. Be "
    "objective and call out unsupported claims. Always report via the submit_grade tool."
)


def _context_text(retrieved: list[RetrievedChunk]) -> str:
    if not retrieved:
        return "(no sources retrieved)"
    return "\n\n".join(f"[{r.index}] ({r.filename}) {r.text}" for r in retrieved)


def heuristic_grade(item: DatasetItem, retrieved: list[RetrievedChunk], answer: str) -> Grade:
    """Deterministic fallback grade — no LLM. Real signal, coarse resolution."""
    refused = looks_like_refusal(answer)
    context = _context_text(retrieved)
    groundedness = token_recall(context, answer)  # are the answer's tokens found in the context?
    if item.answerable:
        correctness = token_recall(answer, item.reference_answer)
    else:
        # For unanswerable questions the "correct" behaviour is to refuse.
        correctness = 1.0 if refused else 0.0
    return Grade(
        groundedness=round(groundedness, 4),
        correctness=round(correctness, 4),
        refused=refused,
        reasoning="heuristic: token-overlap grade",
    )


async def llm_grade(
    client: LLMClient, item: DatasetItem, retrieved: list[RetrievedChunk], answer: str
) -> Grade:
    """LLM-as-judge. Falls back to the heuristic if the model won't produce a grade."""
    reference = item.reference_answer or (
        "(No answer exists in the knowledge base — the assistant SHOULD refuse or escalate.)"
    )
    user = (
        f"Question:\n{item.question}\n\n"
        f"Retrieved context:\n{_context_text(retrieved)}\n\n"
        f"Reference answer:\n{reference}\n\n"
        f"Assistant's answer:\n{answer or '(empty)'}\n\n"
        "Grade the assistant's answer via submit_grade."
    )
    messages = [
        LLMMessage(role="system", content=_JUDGE_SYSTEM),
        LLMMessage(role="user", content=user),
    ]
    turn = await client.complete_with_tools(messages, [_GRADE_TOOL], max_tokens=400)

    args: dict | None = None
    for tc in turn.tool_calls:
        if tc.name == "submit_grade":
            args = tc.arguments
            break
    if args is None and turn.text.strip():
        try:  # some providers emit JSON as text instead of a tool call
            args = json.loads(turn.text[turn.text.find("{") : turn.text.rfind("}") + 1])
        except (json.JSONDecodeError, ValueError):
            args = None
    if args is None:
        return heuristic_grade(item, retrieved, answer)

    def _clamp(v: object) -> float:
        try:
            return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    return Grade(
        groundedness=round(_clamp(args.get("groundedness")), 4),
        correctness=round(_clamp(args.get("correctness")), 4),
        refused=bool(args.get("refused", looks_like_refusal(answer))),
        reasoning=str(args.get("reasoning", ""))[:300],
    )
