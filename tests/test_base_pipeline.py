"""Tests for BaseAnalystPipeline — shared execution lifecycle.

Verifies that the common lifecycle behaves correctly and that concrete
analysts correctly inherit from it.

All tests are deterministic and make zero external API calls.
"""

from pathlib import Path

import pytest

from investiq.analysts.base_pipeline import BaseAnalystPipeline
from investiq.analysts.financial_analyst import FinancialAnalystPipeline
from investiq.analysts.asset_quality_analyst import AssetQualityAnalyst
from investiq.analysts.registry import AnalystRegistry
from investiq.analysts.base import ResearchAnalyst
from investiq.llm.cache import MemoryLLMCache, build_cache_key
from investiq.llm.cost import CostTracker
from investiq.llm.mock import MockLLMProvider
from investiq.models.analyst_input import AnalystInput
from investiq.models.research import (
    FindingCategory,
    ResearchFinding,
    ResearchFindingResponse,
)
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
from investiq.research.validator import ValidationError

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


@pytest.fixture
def synthetic_input():
    """Create a standard AnalystInput with HDFCBANK synthetic data."""
    from investiq.calculators.bank_metrics import compute_bank_metrics
    from investiq.data.loader import load_financial_data

    data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
    metrics = compute_bank_metrics(data)[-1]
    evidence = get_synthetic_hdfcbank_evidence()
    return AnalystInput(
        company=data.company,
        latest_metrics=metrics,
        evidence_items=evidence,
    )
class TestBaseAnalystPipelineConstruction:
    """BaseAnalystPipeline construction."""

    def test_cannot_instantiate_base(self):
        """BaseAnalystPipeline cannot be instantiated directly (abstract)."""
        with pytest.raises(TypeError, match="abstract"):
            BaseAnalystPipeline(provider=MockLLMProvider(simulated_latency_ms=0.0))  # type: ignore

    def test_constructor_signature(self):
        """Constructor accepts provider, cache, cost_tracker."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        cost_tracker = CostTracker()
        analyst = FinancialAnalystPipeline(
            provider=provider, cache=cache, cost_tracker=cost_tracker,
        )
        assert analyst.provider is provider
        assert analyst.cache is cache
        assert analyst.cost_tracker is cost_tracker

    def test_default_cost_tracker_created(self):
        """CostTracker is created if not provided."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = FinancialAnalystPipeline(provider=provider)
        assert analyst.cost_tracker is not None
        assert isinstance(analyst.cost_tracker, CostTracker)


class TestBaseAnalystPipelineConformance:
    """Concrete analysts conform to the hierarchy."""

    def test_financial_is_research_analyst(self):
        """FinancialAnalystPipeline is a ResearchAnalyst."""
        assert issubclass(FinancialAnalystPipeline, ResearchAnalyst)

    def test_asset_quality_is_research_analyst(self):
        """AssetQualityAnalyst is a ResearchAnalyst."""
        assert issubclass(AssetQualityAnalyst, ResearchAnalyst)

    def test_financial_is_base_analyst(self):
        """FinancialAnalystPipeline is a BaseAnalystPipeline."""
        assert issubclass(FinancialAnalystPipeline, BaseAnalystPipeline)

    def test_asset_quality_is_base_analyst(self):
        """AssetQualityAnalyst is a BaseAnalystPipeline."""
        assert issubclass(AssetQualityAnalyst, BaseAnalystPipeline)

    def test_both_can_be_registered(self):
        """Both analysts can be registered in AnalystRegistry."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        registry = AnalystRegistry()
        registry.register("financial_analyst", FinancialAnalystPipeline(provider=provider))
        registry.register("asset_quality_analyst", AssetQualityAnalyst(provider=provider))
        assert "financial_analyst" in registry.list()
        assert "asset_quality_analyst" in registry.list()

    def test_both_are_research_analyst_instances(self):
        """Both analyst instances are ResearchAnalyst instances."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        assert isinstance(FinancialAnalystPipeline(provider=provider), ResearchAnalyst)
class TestBaseAnalystPipelineLifecycle:
    """Common lifecycle behavior."""

    def test_run_returns_list_of_findings(self, synthetic_input):
        """run() returns list[ResearchFinding]."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = FinancialAnalystPipeline(provider=provider)
        findings = analyst.run(synthetic_input)
        assert isinstance(findings, list)
        assert len(findings) > 0
        assert all(isinstance(f, ResearchFinding) for f in findings)

    def test_cache_hit(self, synthetic_input):
        """Cache hit returns findings without calling provider twice."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        cost_tracker = CostTracker()
        analyst = FinancialAnalystPipeline(
            provider=provider, cache=cache, cost_tracker=cost_tracker,
        )
        findings1 = analyst.run(synthetic_input)
        assert len(findings1) > 0
        assert cost_tracker.total_calls == 1
        assert cost_tracker.total_cache_hits == 0
        findings2 = analyst.run(synthetic_input)
        assert len(findings2) > 0
        assert cost_tracker.total_calls == 2
        assert cost_tracker.total_cache_hits == 1

    def test_cache_miss_records_cost(self, synthetic_input):
        """Cache miss records a call with cost."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cost_tracker = CostTracker()
        analyst = FinancialAnalystPipeline(provider=provider, cost_tracker=cost_tracker)
        analyst.run(synthetic_input)
        assert cost_tracker.total_calls == 1
        assert cost_tracker.total_cost_usd == 0.0

    def test_preset_response_parsed(self, synthetic_input):
        """A preset ResearchFindingResponse is parsed correctly."""
        preset = ResearchFindingResponse(
            findings=[
                ResearchFinding(
                    analyst="financial_analyst", title="Test Finding",
                    statement="Test.", confidence=0.5,
                    evidence_ids=["SYN-HDFCBANK-ROE-001"],
                    category=FindingCategory.PROFITABILITY,
                ),
            ],
        )
        provider = MockLLMProvider(simulated_latency_ms=0.0, preset_response=preset)
        analyst = FinancialAnalystPipeline(provider=provider)
        findings = analyst.run(synthetic_input)
        assert len(findings) == 1
        assert findings[0].title == "Test Finding"

    def test_invalid_evidence_id_rejected(self, synthetic_input):
        """Invalid evidence IDs are rejected by validation."""
        preset = ResearchFindingResponse(
            findings=[
                ResearchFinding(
                    analyst="financial_analyst", title="Bad Evidence",
                    statement="Bad.", confidence=0.5,
                    evidence_ids=["INVALID-ID"],
                    category=FindingCategory.PROFITABILITY,
                ),
            ],
        )
        provider = MockLLMProvider(simulated_latency_ms=0.0, preset_response=preset)
        analyst = FinancialAnalystPipeline(provider=provider)
        with pytest.raises(ValidationError, match="invalid evidence_id"):
            analyst.run(synthetic_input)


class TestBaseAnalystPipelineCacheKeyIdentity:
    """Cache key construction is correct."""

    def test_cache_key_uses_analyst_type(self, synthetic_input):
        """Cache key is a non-empty hex string."""
        key = build_cache_key(
            ticker=synthetic_input.company.ticker,
            analyst_type="financial_analyst",
            normalized_input=synthetic_input.model_dump_json(),
            prompt_version="financial_analyst_v1",
            model_config={"temperature": 0.2, "max_tokens": 700},
        )
        assert isinstance(key, str) and len(key) > 0
        assert all(c in "0123456789abcdef" for c in key)

    def test_different_analyst_types_different_keys(self, synthetic_input):
        """Different analyst types produce different cache keys."""
        fin_key = build_cache_key(
            ticker=synthetic_input.company.ticker,
            analyst_type="financial_analyst",
            normalized_input=synthetic_input.model_dump_json(),
            prompt_version="financial_analyst_v1",
            model_config={"temperature": 0.2, "max_tokens": 700},
        )
        aq_key = build_cache_key(
            ticker=synthetic_input.company.ticker,
            analyst_type="asset_quality_analyst",
            normalized_input=synthetic_input.model_dump_json(),
            prompt_version="asset_quality_analyst_v1",
            model_config={"temperature": 0.2, "max_tokens": 700},
        )
        assert fin_key != aq_key


class TestBaseAnalystPipelineAnalystProperties:
    """Analyst-specific properties are correct."""

    def test_financial_analyst_properties(self):
        """FinancialAnalystPipeline exposes expected properties."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = FinancialAnalystPipeline(provider=provider)
        assert analyst._model_name == "mock-financial-analyst-v1"
        assert analyst._analyst_type == "financial_analyst"
        assert analyst._prompt_version == "financial_analyst_v1"

    def test_asset_quality_analyst_properties(self):
        """AssetQualityAnalyst exposes expected properties."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        assert analyst._model_name == "mock-asset-quality-analyst-v1"
        assert analyst._analyst_type == "asset_quality_analyst"
        assert analyst._prompt_version == "asset_quality_analyst_v1"
        assert isinstance(AssetQualityAnalyst(provider=provider), ResearchAnalyst)