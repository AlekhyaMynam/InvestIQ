"""LLM abstraction layer for InvestIQ.

Provides provider abstraction, mock provider, cost tracking, caching,
and cost safety guard.
"""

from investiq.llm.base import CostGuardError, LLMProvider, LLMRequest, LLMResponse
from investiq.llm.cache import LLMCache, MemoryLLMCache
from investiq.llm.cost import CostTracker, ModelPricing
from investiq.llm.gemini import GeminiProvider
from investiq.llm.guard import enforce_offline_mode
from investiq.llm.mock import MockLLMProvider

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "CostGuardError",
    "MockLLMProvider",
    "GeminiProvider",
    "ModelPricing",
    "CostTracker",
    "LLMCache",
    "MemoryLLMCache",
    "enforce_offline_mode",
]
