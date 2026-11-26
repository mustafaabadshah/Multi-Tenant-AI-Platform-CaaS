"""Pricing calculation engine for verifiable AI model cost estimation.

Provides deterministic token pricing rates per 1M tokens based on published provider rates.
Does not make remote API calls. Accurately labels costs as 'zero_cost', 'known', or 'unknown'.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelPricing:
    provider: str
    model: str
    input_rate_per_m: float   # USD per 1,000,000 input tokens
    output_rate_per_m: float  # USD per 1,000,000 output tokens
    effective_date: str
    currency: str = "USD"


# Published standard pricing catalog (per 1M tokens)
# Note: For BYOK, this reflects estimated provider consumption cost, NOT platform billing.
KNOWN_MODEL_PRICING: dict[tuple[str, str], ModelPricing] = {
    # Mock Provider
    ("mock", "mock-chat-v1"): ModelPricing("mock", "mock-chat-v1", 0.0, 0.0, "2026-01-01"),
    ("mock", "mock-chat-v2"): ModelPricing("mock", "mock-chat-v2", 0.0, 0.0, "2026-01-01"),
    ("mock", "auto"): ModelPricing("mock", "auto", 0.0, 0.0, "2026-01-01"),

    # OpenAI Models
    ("openai", "gpt-4o"): ModelPricing("openai", "gpt-4o", 2.50, 10.00, "2024-11-01"),
    ("openai", "gpt-4o-mini"): ModelPricing("openai", "gpt-4o-mini", 0.15, 0.60, "2024-07-18"),
    ("openai", "gpt-4-turbo"): ModelPricing("openai", "gpt-4-turbo", 10.00, 30.00, "2024-04-09"),
    ("openai", "o1"): ModelPricing("openai", "o1", 15.00, 60.00, "2024-12-17"),
    ("openai", "o1-mini"): ModelPricing("openai", "o1-mini", 3.00, 12.00, "2024-09-12"),

    # Anthropic Models
    ("anthropic", "claude-3-5-sonnet-20241022"): ModelPricing("anthropic", "claude-3-5-sonnet-20241022", 3.00, 15.00, "2024-10-22"),
    ("anthropic", "claude-3-5-sonnet"): ModelPricing("anthropic", "claude-3-5-sonnet", 3.00, 15.00, "2024-10-22"),
    ("anthropic", "claude-3-5-haiku"): ModelPricing("anthropic", "claude-3-5-haiku", 0.80, 4.00, "2024-10-22"),
    ("anthropic", "claude-3-opus"): ModelPricing("anthropic", "claude-3-opus", 15.00, 75.00, "2024-03-01"),

    # Google Gemini Models
    ("gemini", "gemini-1.5-pro"): ModelPricing("gemini", "gemini-1.5-pro", 1.25, 5.00, "2024-05-14"),
    ("gemini", "gemini-1.5-flash"): ModelPricing("gemini", "gemini-1.5-flash", 0.075, 0.30, "2024-05-14"),
    ("gemini", "gemini-2.0-flash"): ModelPricing("gemini", "gemini-2.0-flash", 0.10, 0.40, "2024-12-11"),

    # Groq Models
    ("groq", "llama-3.3-70b-versatile"): ModelPricing("groq", "llama-3.3-70b-versatile", 0.59, 0.79, "2024-12-06"),
    ("groq", "llama-3.1-8b-instant"): ModelPricing("groq", "llama-3.1-8b-instant", 0.05, 0.08, "2024-07-23"),
}


def estimate_request_cost(
    provider: Optional[str],
    model: Optional[str],
    input_tokens: int,
    output_tokens: int,
) -> tuple[Optional[float], str]:
    """Calculate estimated cost for a given request.

    Returns:
        tuple[Optional[float], str]:
            (estimated_cost_usd, pricing_status)
            pricing_status can be: 'zero_cost', 'known', or 'unknown'
    """
    if not provider:
        return None, "unknown"

    prov_clean = provider.strip().lower()
    model_clean = (model or "auto").strip().lower()

    if prov_clean == "mock":
        return 0.0, "zero_cost"

    # Match exact or normalized model
    pricing = KNOWN_MODEL_PRICING.get((prov_clean, model_clean))
    if not pricing:
        # Check prefix matches (e.g. gpt-4o-mini-2024-07-18 -> gpt-4o-mini)
        for (p, m), p_info in KNOWN_MODEL_PRICING.items():
            if p == prov_clean and model_clean.startswith(m):
                pricing = p_info
                break

    if not pricing:
        return None, "unknown"

    if pricing.input_rate_per_m == 0.0 and pricing.output_rate_per_m == 0.0:
        return 0.0, "zero_cost"

    cost = (input_tokens * pricing.input_rate_per_m / 1_000_000.0) + (
        output_tokens * pricing.output_rate_per_m / 1_000_000.0
    )
    return round(cost, 6), "known"
