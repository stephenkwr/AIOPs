"""Token pricing, USD per 1M tokens (input, output).

Free-tier models are $0 here; the list-price equivalent is noted in comments so a
later phase can surface a "would-be cost" in the trace.
"""

PRICING: dict[str, tuple[float, float]] = {
    "gemini-flash-latest": (0.0, 0.0),  # free tier (list ~ $0.075 / $0.30)
    "gemini-2.5-flash-lite": (0.0, 0.0),
    "llama-3.3-70b-versatile": (0.0, 0.0),  # Groq free tier
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "fake-llm": (0.0, 0.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICING.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
