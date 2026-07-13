from __future__ import annotations

from llm.provider import TokenUsage

# USD per 1M tokens (prompt, completion). Illustrative snapshot for cost-tracking
# in the demo dashboard, not a billing-accurate source of truth -- Groq's
# published pricing changes independently of this file. Local providers
# (Ollama) have no per-token cost, so they simply aren't listed here.
_GROQ_PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
}


def estimate_cost_usd(provider_name: str, model: str, usage: TokenUsage) -> float | None:
    """Returns None when cost isn't meaningful (local provider) or the model
    isn't in the pricing table, rather than silently reporting 0 -- callers
    should treat None as "unknown," not "free."
    """
    if provider_name == "ollama":
        return 0.0
    if provider_name != "groq":
        return None
    pricing = _GROQ_PRICING_PER_MILLION.get(model)
    if pricing is None or usage.prompt_tokens is None or usage.completion_tokens is None:
        return None
    prompt_rate, completion_rate = pricing
    return (usage.prompt_tokens / 1_000_000) * prompt_rate + (usage.completion_tokens / 1_000_000) * completion_rate
