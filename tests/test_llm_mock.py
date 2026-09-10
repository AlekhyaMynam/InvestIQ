"""Tests for Mock LLM Provider, Cost Tracker, Cache, and Cost Safety Guard."""

import pytest

from investiq.llm.base import CostGuardError, LLMRequest
from investiq.llm.cache import MemoryLLMCache, build_cache_key
from investiq.llm.cost import CostTracker, ModelPricing
from investiq.llm.guard import assert_provider_allowed
from investiq.llm.mock import MockLLMProvider
from investiq.models.research import ResearchFinding


class TestMockLLMProvider:
    """Test MockLLMProvider behavior."""

    def test_mock_provider_makes_zero_network_calls(self):
        """Mock provider returns deterministic response without network calls."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        req = LLMRequest(prompt="Analyze HDFCBANK", model="mock-financial-analyst-v1")

        resp = provider.generate_structured(req, list)

        assert resp.model == "mock-financial-analyst-v1"
        assert resp.input_tokens > 0
        assert resp.output_tokens > 0
        assert resp.estimated_cost == 0.0
        assert resp.cache_hit is False
        assert len(resp.output) > 0

    def test_deterministic_responses(self):
        """Sequential calls with identical input produce identical output."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        req = LLMRequest(prompt="Analyze HDFCBANK", model="mock-financial-analyst-v1")

        resp1 = provider.generate_structured(req, list)
        resp2 = provider.generate_structured(req, list)

        assert resp1.output == resp2.output


class TestCostTracker:
    """Test CostTracker token usage and cost accounting."""

    def test_record_call_and_pricing(self):
        tracker = CostTracker()
        tracker.pricing_registry["test-model"] = ModelPricing(
            model_id="test-model",
            input_price_per_1m=10.0,
            output_price_per_1m=30.0,
        )

        cost = tracker.record_call(
            model="test-model",
            input_tokens=100_000,   # (100k / 1M) * 10 = $1.00
            output_tokens=100_000,  # (100k / 1M) * 30 = $3.00
            cache_hit=False,
        )

        assert cost == pytest.approx(4.00)
        assert tracker.total_calls == 1
        assert tracker.total_input_tokens == 100_000
        assert tracker.total_output_tokens == 100_000
        assert tracker.total_cost_usd == pytest.approx(4.00)

    def test_cache_hit_cost_is_zero(self):
        tracker = CostTracker()
        tracker.pricing_registry["test-model"] = ModelPricing(
            model_id="test-model",
            input_price_per_1m=10.0,
            output_price_per_1m=30.0,
        )

        cost = tracker.record_call(
            model="test-model",
            input_tokens=100_000,
            output_tokens=100_000,
            cache_hit=True,
        )

        assert cost == 0.0
        assert tracker.total_cache_hits == 1
        assert tracker.total_cost_usd == 0.0


class TestLLMCache:
    """Test in-memory LLMCache and key generation."""

    def test_cache_hit_and_miss(self):
        cache = MemoryLLMCache()
        key = build_cache_key("HDFCBANK", "financial_analyst", "payload", "v1", {})

        assert cache.get(key) is None

        provider = MockLLMProvider(simulated_latency_ms=0.0)
        req = LLMRequest(prompt="test", model="mock-financial-analyst-v1")
        resp = provider.generate_structured(req, list)

        cache.set(key, resp)
        cached = cache.get(key)

        assert cached is not None
        assert cached.cache_hit is True
        assert cached.output == resp.output


class TestCostSafetyGuard:
    """Test cost safety guard against accidental real LLM API calls."""

    def test_mock_provider_allowed(self):
        """Mock providers starting with 'mock' are always allowed."""
        assert_provider_allowed("mock-financial-analyst-v1")

    def test_real_provider_blocked_in_offline_mode(self, monkeypatch):
        """Requesting real Gemini/OpenAI provider in offline mode raises CostGuardError."""
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "false")

        with pytest.raises(CostGuardError, match="Attempted to invoke real LLM provider"):
            assert_provider_allowed("gemini-1.5-pro")
