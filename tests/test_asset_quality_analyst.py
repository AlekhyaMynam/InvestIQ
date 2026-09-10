"""Tests for AssetQualityAnalyst — specialist bank asset quality pipeline.

All tests are deterministic and make zero external API calls.
"""

from pathlib import Path

import pytest

from investiq.analysts.asset_quality_analyst import AssetQualityAnalyst
from investiq.analysts.base import ResearchAnalyst
from investiq.llm.cache import MemoryLLMCache
from investiq.llm.cost import CostTracker
from investiq.llm.mock import MockLLMProvider
from investiq.models.analyst_input import AnalystInput
from investiq.models.research import (
    FindingCategory,
    ResearchFinding,
    ResearchFindingResponse,
)
from investiq.prompts.asset_quality_analyst import (
    ASSET_QUALITY_SYSTEM_INSTRUCTION,
    render_asset_quality_analyst_prompt,
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
        research_objective="Assess HDFC Bank asset quality and credit risk profile.",
        )


class TestAssetQualityAnalystInterface:
    """AssetQualityAnalyst conforms to ResearchAnalyst."""

    def test_is_research_analyst(self):
        """AssetQualityAnalyst is a subclass of ResearchAnalyst."""
        assert issubclass(AssetQualityAnalyst, ResearchAnalyst)

    def test_instance_is_research_analyst(self):
        """An AssetQualityAnalyst instance is a ResearchAnalyst."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        assert isinstance(analyst, ResearchAnalyst)


class TestAssetQualityAnalystConstruction:
    """AssetQualityAnalyst construction."""

    def test_constructor_accepts_provider(self):
        """Constructor accepts LLMProvider."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        assert analyst.provider is provider

    def test_constructor_accepts_cache(self):
        """Constructor accepts optional cache."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        analyst = AssetQualityAnalyst(provider=provider, cache=cache)
        assert analyst.cache is cache

    def test_constructor_accepts_cost_tracker(self):
        """Constructor accepts optional cost tracker."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cost_tracker = CostTracker()
        analyst = AssetQualityAnalyst(provider=provider, cost_tracker=cost_tracker)
        assert analyst.cost_tracker is cost_tracker


class TestAssetQualityAnalystPrompt:
    """Prompt rendering."""

    def test_prompt_contains_gross_npa(self, synthetic_input):
        """Rendered prompt contains Gross NPA reference."""
        prompt = render_asset_quality_analyst_prompt(synthetic_input)
        assert "Gross NPA" in prompt

    def test_prompt_contains_net_npa(self, synthetic_input):
        """Rendered prompt contains Net NPA reference."""
        prompt = render_asset_quality_analyst_prompt(synthetic_input)
        assert "Net NPA" in prompt

    def test_prompt_contains_credit_cost(self, synthetic_input):
        """Rendered prompt contains Credit Cost reference."""
        prompt = render_asset_quality_analyst_prompt(synthetic_input)
        assert "Credit Cost" in prompt

    def test_prompt_contains_target_company(self, synthetic_input):
        """Rendered prompt contains company ticker and name."""
        prompt = render_asset_quality_analyst_prompt(synthetic_input)
        assert "HDFCBANK" in prompt
        assert "HDFC Bank" in prompt

    def test_prompt_contains_evidence(self, synthetic_input):
        """Rendered prompt contains evidence items from the input."""
        prompt = render_asset_quality_analyst_prompt(synthetic_input)
        assert "SYN-HDFCBANK-NPA-001" in prompt
        assert "SYN-HDFCBANK-CC-001" in prompt
class TestAssetQualityAnalystExecution:
    """Pipeline execution with MockLLMProvider."""

    def test_run_returns_list_of_research_finding(self, synthetic_input):
        """run() returns list[ResearchFinding]."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        assert isinstance(findings, list)
        assert len(findings) > 0
        assert all(isinstance(f, ResearchFinding) for f in findings)

    def test_analyst_identity_is_asset_quality_analyst(self, synthetic_input):
        """Every finding has analyst == 'asset_quality_analyst'."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        for f in findings:
            assert f.analyst == "asset_quality_analyst"

    def test_findings_have_evidence_ids(self, synthetic_input):
        """Findings reference valid evidence IDs from the input."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        valid_ids = {e.evidence_id for e in synthetic_input.evidence_items}
        for f in findings:
            for eid in f.evidence_ids:
                assert eid in valid_ids

    def test_findings_use_valid_category(self, synthetic_input):
        """Findings use an appropriate FindingCategory."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        valid = {FindingCategory.ASSET_QUALITY, FindingCategory.RISK,
                 FindingCategory.CAPITAL_ADEQUACY, FindingCategory.PROFITABILITY}
        for f in findings:
            assert f.category in valid, f"Unexpected category: {f.category}"

    def test_findings_have_confidence_in_range(self, synthetic_input):
        """Confidence scores are between 0.0 and 1.0."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        for f in findings:
            assert 0.0 <= f.confidence <= 1.0

    def test_all_required_fields_present(self, synthetic_input):
        """All required ResearchFinding fields are populated."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        for f in findings:
            assert f.analyst and f.title and f.statement and f.evidence_ids and f.category

    def test_preset_response_used(self, synthetic_input):
        """A preset response can be injected for custom scenarios."""
        preset = ResearchFindingResponse(
            findings=[
                ResearchFinding(
                    analyst="asset_quality_analyst",
                    title="Custom Test Finding",
                    statement="Custom statement.",
                    confidence=0.75,
                    evidence_ids=["SYN-HDFCBANK-NPA-001"],
                    category=FindingCategory.ASSET_QUALITY,
                ),
            ],
        )
        provider = MockLLMProvider(
            simulated_latency_ms=0.0,
            preset_response=preset,
        )
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        assert len(findings) == 1
        assert findings[0].title == "Custom Test Finding"
        assert findings[0].analyst == "asset_quality_analyst"
class TestAssetQualityAnalystCache:
    """Cache behavior."""

    def test_cache_hit(self, synthetic_input):
        """Cache hit returns findings without calling provider."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        cost_tracker = CostTracker()
        analyst = AssetQualityAnalyst(
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


class TestAssetQualityAnalystValidation:
    """Output validation."""

    def test_invalid_evidence_id_rejected(self, synthetic_input):
        """Invalid evidence IDs are rejected by validation."""
        preset = ResearchFindingResponse(
            findings=[
                ResearchFinding(
                    analyst="asset_quality_analyst", title="Bad Evidence",
                    statement="This has an invalid ID.", confidence=0.5,
                    evidence_ids=["INVALID-EVIDENCE-ID"],
                    category=FindingCategory.ASSET_QUALITY,
                ),
            ],
        )
        provider = MockLLMProvider(simulated_latency_ms=0.0, preset_response=preset)
        analyst = AssetQualityAnalyst(provider=provider)
        with pytest.raises(ValidationError, match="invalid evidence_id"):
            analyst.run(synthetic_input)

    def test_empty_findings(self, synthetic_input):
        """Empty findings list is valid."""
        preset = ResearchFindingResponse(findings=[])
        provider = MockLLMProvider(simulated_latency_ms=0.0, preset_response=preset)
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        assert findings == []


class TestAssetQualityAnalystCostTracking:
    """Cost tracking behavior."""

    def test_cost_tracker_records_call(self, synthetic_input):
        """CostTracker records a call after execution."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cost_tracker = CostTracker()
        analyst = AssetQualityAnalyst(provider=provider, cost_tracker=cost_tracker)
        analyst.run(synthetic_input)
        assert cost_tracker.total_calls == 1
        assert cost_tracker.total_cost_usd == 0.0


class TestAssetQualityAnalystMockProvider:
    """MockLLMProvider makes zero network calls."""

    def test_no_external_api_calls(self, synthetic_input):
        """MockLLMProvider makes zero network calls."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = AssetQualityAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        assert len(findings) > 0
        assert all(f.analyst == "asset_quality_analyst" for f in findings)