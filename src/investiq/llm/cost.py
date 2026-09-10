"""Cost tracking and model pricing metadata.

Tracks token consumption, cache hits, and estimated dollar costs across calls.
Pricing metadata is configurable and not hardcoded into business logic.
"""

from pydantic import BaseModel, Field


class ModelPricing(BaseModel):
    """Pricing metadata for a specific LLM model (costs per 1,000,000 tokens in USD)."""

    model_id: str
    input_price_per_1m: float = 0.0      # USD per 1M input tokens
    output_price_per_1m: float = 0.0     # USD per 1M output tokens

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost in USD for a given token usage."""
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_1m
        return round(input_cost + output_cost, 6)


# Default pricing registry (configurable)
DEFAULT_PRICING_REGISTRY: dict[str, ModelPricing] = {
    "mock-financial-analyst-v1": ModelPricing(
        model_id="mock-financial-analyst-v1",
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
    ),
    "gemini-3.5-flash-lite": ModelPricing(
        model_id="gemini-3.5-flash-lite",
        input_price_per_1m=0.30,
        output_price_per_1m=2.50,
    ),
    "gemini-2.5-flash-lite": ModelPricing(
        model_id="gemini-2.5-flash-lite",
        input_price_per_1m=0.075,
        output_price_per_1m=0.30,
    ),
    "gemini-1.5-pro": ModelPricing(
        model_id="gemini-1.5-pro",
        input_price_per_1m=3.50,
        output_price_per_1m=10.50,
    ),
    "gemini-1.5-flash": ModelPricing(
        model_id="gemini-1.5-flash",
        input_price_per_1m=0.35,
        output_price_per_1m=1.05,
    ),
}


class ModelUsageSummary(BaseModel):
    """Usage summary aggregated for a single model."""

    calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0


class CostTracker(BaseModel):
    """Session or application-level cost tracker.

    Tracks API calls, cache hits, token usage, and costs across models.
    """

    pricing_registry: dict[str, ModelPricing] = Field(
        default_factory=lambda: dict(DEFAULT_PRICING_REGISTRY)
    )
    total_calls: int = 0
    total_cache_hits: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    by_model: dict[str, ModelUsageSummary] = Field(default_factory=dict)

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_hit: bool = False,
    ) -> float:
        """Record an LLM call and return its estimated cost."""
        pricing = self.pricing_registry.get(
            model, ModelPricing(model_id=model, input_price_per_1m=0.0, output_price_per_1m=0.0)
        )

        cost = 0.0 if cache_hit else pricing.calculate_cost(input_tokens, output_tokens)

        self.total_calls += 1
        if cache_hit:
            self.total_cache_hits += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd = round(self.total_cost_usd + cost, 6)

        if model not in self.by_model:
            self.by_model[model] = ModelUsageSummary()

        summary = self.by_model[model]
        summary.calls += 1
        if cache_hit:
            summary.cache_hits += 1
        summary.input_tokens += input_tokens
        summary.output_tokens += output_tokens
        summary.total_cost_usd = round(summary.total_cost_usd + cost, 6)

        return cost
