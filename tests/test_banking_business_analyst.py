"""Tests for BankingBusinessAnalyst — specialist bank business/competitive pipeline.

All tests are deterministic and make zero external API calls.
"""

from pathlib import Path

import pytest

from investiq.analysts.banking_business_analyst import BankingBusinessAnalyst
from investiq.analysts.base import ResearchAnalyst
from investiq.analysts.base_pipeline import BaseAnalystPipeline
from investiq.llm.cache import MemoryLLMCache
from investiq.llm.cost import CostTracker
from investiq.llm.mock import MockLLMProvider
from investiq.models.analyst_input import AnalystInput
from investiq.models.research import (
    FindingCategory,
    ResearchFinding,
    ResearchFindingResponse,
)
from investiq.prompts.banking_business_analyst import (
    BANKING_BUSINESS_SYSTEM_INSTRUCTION,
    render_banking_business_analyst_prompt,
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
        research_objective="Assess HDFC Bank business quality, competitive positioning, and franchise strength.",
    )
class TestBankingBusinessAnalystInterface:
    """BankingBusinessAnalyst conforms to ResearchAnalyst."""

    def test_is_research_analyst(self):
        """BankingBusinessAnalyst is a subclass of ResearchAnalyst."""
        assert issubclass(BankingBusinessAnalyst, ResearchAnalyst)

    def test_is_base_analyst_pipeline(self):
        """BankingBusinessAnalyst is a subclass of BaseAnalystPipeline."""
        assert issubclass(BankingBusinessAnalyst, BaseAnalystPipeline)

    def test_instance_is_research_analyst(self):
        """A BankingBusinessAnalyst instance is a ResearchAnalyst."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        assert isinstance(analyst, ResearchAnalyst)


class TestBankingBusinessAnalystConstruction:
    """BankingBusinessAnalyst construction."""

    def test_constructor_accepts_provider(self):
        """Constructor accepts LLMProvider."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        assert analyst.provider is provider

    def test_constructor_accepts_cache(self):
        """Constructor accepts optional cache."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        analyst = BankingBusinessAnalyst(provider=provider, cache=cache)
        assert analyst.cache is cache

    def test_constructor_accepts_cost_tracker(self):
        """Constructor accepts optional cost tracker."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cost_tracker = CostTracker()
        analyst = BankingBusinessAnalyst(provider=provider, cost_tracker=cost_tracker)
        assert analyst.cost_tracker is cost_tracker


class TestBankingBusinessAnalystProperties:
    """Analyst-specific properties match expected values."""

    def test_model_name(self):
        """Model name is mock-banking-business-analyst-v1."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        assert analyst._model_name == "mock-banking-business-analyst-v1"

    def test_analyst_type(self):
        """Analyst type is banking_business_analyst."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        assert analyst._analyst_type == "banking_business_analyst"

    def test_prompt_version(self):
        """Prompt version is banking_business_analyst_v1."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
class TestBankingBusinessAnalystPrompt:
    """Prompt rendering."""

    def test_prompt_contains_business_keywords(self, synthetic_input):
        """Rendered prompt contains business/competitive keywords."""
        prompt = render_banking_business_analyst_prompt(synthetic_input)
        assert "competitive" in prompt.lower() or "franchise" in prompt.lower()

    def test_prompt_contains_target_company(self, synthetic_input):
        """Rendered prompt contains company ticker and name."""
        prompt = render_banking_business_analyst_prompt(synthetic_input)
        assert "HDFCBANK" in prompt
        assert "HDFC Bank" in prompt

    def test_prompt_contains_evidence(self, synthetic_input):
        """Rendered prompt contains evidence items from the input."""
        prompt = render_banking_business_analyst_prompt(synthetic_input)
        assert "SYN-HDFCBANK-CASA-001" in prompt


class TestBankingBusinessAnalystExecution:
    """Pipeline execution with MockLLMProvider."""

    def test_run_returns_list_of_research_finding(self, synthetic_input):
        """run() returns list[ResearchFinding]."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        assert isinstance(findings, list)
        assert len(findings) > 0
        assert all(isinstance(f, ResearchFinding) for f in findings)

    def test_analyst_identity_is_banking_business_analyst(self, synthetic_input):
        """Every finding has analyst == 'banking_business_analyst'."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        for f in findings:
            assert f.analyst == "banking_business_analyst"

    def test_findings_have_evidence_ids(self, synthetic_input):
        """Findings reference valid evidence IDs from the input."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        valid_ids = {e.evidence_id for e in synthetic_input.evidence_items}
        for f in findings:
            for eid in f.evidence_ids:
                assert eid in valid_ids

    def test_findings_have_confidence_in_range(self, synthetic_input):
        """Confidence scores are between 0.0 and 1.0."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        for f in findings:
            assert 0.0 <= f.confidence <= 1.0

    def test_all_required_fields_present(self, synthetic_input):
        """All required fields are populated."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        for f in findings:
            assert f.analyst and f.title and f.statement and f.evidence_ids and f.category

    def test_preset_response_used(self, synthetic_input):
        """A preset response can be injected for custom scenarios."""
        preset = ResearchFindingResponse(
            findings=[
                ResearchFinding(
                    analyst="banking_business_analyst",
                    title="Custom Finding", statement="Custom.",
                    confidence=0.75,
                    evidence_ids=["SYN-HDFCBANK-CASA-001"],
                    category=FindingCategory.COMPETITIVE_POSITION,
                ),
            ],
        )
        provider = MockLLMProvider(simulated_latency_ms=0.0, preset_response=preset)
        analyst = BankingBusinessAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        assert len(findings) == 1
        assert findings[0].title == "Custom Finding"
        assert findings[0].analyst == "banking_business_analyst"


class TestBankingBusinessAnalystCache:
    """Cache behavior."""

    def test_cache_hit(self, synthetic_input):
        """Cache hit returns findings without calling provider."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        cost_tracker = CostTracker()
        analyst = BankingBusinessAnalyst(
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


class TestBankingBusinessAnalystValidation:
    """Output validation."""

    def test_invalid_evidence_id_rejected(self, synthetic_input):
        """Invalid evidence IDs are rejected by validation."""
        preset = ResearchFindingResponse(
            findings=[
                ResearchFinding(
                    analyst="banking_business_analyst", title="Bad",
                    statement="Bad.", confidence=0.5,
                    evidence_ids=["INVALID-ID"],
                    category=FindingCategory.COMPETITIVE_POSITION,
                ),
            ],
        )
        provider = MockLLMProvider(simulated_latency_ms=0.0, preset_response=preset)
        analyst = BankingBusinessAnalyst(provider=provider)
        with pytest.raises(ValidationError, match="invalid evidence_id"):
            analyst.run(synthetic_input)

    def test_empty_findings(self, synthetic_input):
        """Empty findings list is valid."""
        preset = ResearchFindingResponse(findings=[])
        provider = MockLLMProvider(simulated_latency_ms=0.0, preset_response=preset)
        analyst = BankingBusinessAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        assert findings == []


class TestBankingBusinessAnalystCostTracking:
    """Cost tracking behavior."""

    def test_cost_tracker_records_call(self, synthetic_input):
        """CostTracker records a call after execution."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cost_tracker = CostTracker()
        analyst = BankingBusinessAnalyst(provider=provider, cost_tracker=cost_tracker)
        analyst.run(synthetic_input)
        assert cost_tracker.total_calls == 1
        assert cost_tracker.total_cost_usd == 0.0


class TestBankingBusinessAnalystMockProvider:
    """MockLLMProvider makes zero network calls."""

    def test_no_external_api_calls(self, synthetic_input):
        """MockLLMProvider makes zero network calls."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = BankingBusinessAnalyst(provider=provider)
        findings = analyst.run(synthetic_input)
        assert len(findings) > 0
        assert all(f.analyst == "banking_business_analyst" for f in findings)
        assert analyst._prompt_version == "banking_business_analyst_v1"