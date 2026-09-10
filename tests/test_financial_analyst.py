"""Tests for Financial Analyst Pipeline, Prompt Rendering, and Output Validator."""

from pathlib import Path

import pytest

from investiq.analysts.financial_analyst import FinancialAnalystPipeline
from investiq.calculators.bank_metrics import compute_bank_metrics
from investiq.data.loader import load_financial_data
from investiq.llm.cache import MemoryLLMCache
from investiq.llm.cost import CostTracker
from investiq.llm.mock import MockLLMProvider
from investiq.models.analyst_input import AnalystInput
from investiq.models.evidence import EvidenceItem, EvidenceTag
from investiq.models.research import FindingCategory, ResearchFinding, ResearchFindingResponse
from investiq.prompts.financial_analyst import render_financial_analyst_prompt
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
from investiq.research.validator import ValidationError, validate_analyst_finding


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


@pytest.fixture
def synthetic_hdfc_input():
    data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
    metrics = compute_bank_metrics(data)[-1]  # FY2025
    evidence = get_synthetic_hdfcbank_evidence()

    return AnalystInput(
        company=data.company,
        latest_metrics=metrics,
        evidence_items=evidence,
        research_objective="Analyze asset quality and liability franchise.",
    )


class TestPromptRendering:
    """Test versioned prompt template rendering."""

    def test_prompt_rendering_structure(self, synthetic_hdfc_input):
        prompt = render_financial_analyst_prompt(synthetic_hdfc_input)

        assert "HDFCBANK" in prompt
        assert "HDFC Bank Limited" in prompt
        assert "BANK" in prompt
        assert "SYN-HDFCBANK-CASA-001" in prompt
        assert "CASA Ratio" in prompt


class TestOutputValidation:
    """Test output validation rules for research findings."""

    def test_valid_finding_passes(self, synthetic_hdfc_input):
        finding = ResearchFinding(
            analyst="financial_analyst",
            title="Strong CASA Ratio",
            statement="CASA ratio at 35% provides low-cost funding.",
            confidence=0.85,
            evidence_ids=["SYN-HDFCBANK-CASA-001"],
            category=FindingCategory.LIABILITY_FRANCHISE,
        )
        # Should not raise
        validate_analyst_finding(finding, synthetic_hdfc_input.evidence_items)

    def test_invalid_evidence_id_rejected(self, synthetic_hdfc_input):
        finding = ResearchFinding(
            analyst="financial_analyst",
            title="Invalid Evidence Test",
            statement="Test statement",
            confidence=0.85,
            evidence_ids=["INVALID-ID-999"],
            category=FindingCategory.PROFITABILITY,
        )
        with pytest.raises(ValidationError, match="references invalid evidence_id"):
            validate_analyst_finding(finding, synthetic_hdfc_input.evidence_items)

    def test_invalid_confidence_rejected(self, synthetic_hdfc_input):
        with pytest.raises(Exception):
            ResearchFinding(
                analyst="financial_analyst",
                title="Invalid Confidence",
                statement="Test statement",
                confidence=1.5,  # > 1.0 violates Pydantic Field ge=0.0, le=1.0
                evidence_ids=["SYN-HDFCBANK-CASA-001"],
                category=FindingCategory.PROFITABILITY,
            )

    def test_prohibited_buy_recommendation_rejected(self, synthetic_hdfc_input):
        finding = ResearchFinding(
            analyst="financial_analyst",
            title="BUY Recommendation on HDFC Bank",
            statement="We recommend BUY with price target ₹2200.",
            confidence=0.90,
            evidence_ids=["SYN-HDFCBANK-CASA-001"],
            category=FindingCategory.VALUATION,
        )
        with pytest.raises(ValidationError, match="prohibited trading/investment recommendation"):
            validate_analyst_finding(finding, synthetic_hdfc_input.evidence_items)


class TestSyntheticProvenance:
    """Test that synthetic evidence fixture is explicitly marked SYNTHETIC."""

    def test_synthetic_evidence_provenance(self):
        evidence_list = get_synthetic_hdfcbank_evidence()
        assert len(evidence_list) > 0
        for ev in evidence_list:
            assert ev.evidence_id.startswith("SYN-")
            assert "Synthetic" in ev.source or ev.source_url.startswith("https://investiq.internal/synthetic")


class TestFinancialAnalystPipeline:
    """Integration test for full offline Financial Analyst Pipeline."""

    def test_pipeline_passes_research_finding_response_schema(self, synthetic_hdfc_input):
        """Pipeline must pass ResearchFindingResponse (not bare list) as the schema."""
        recorded = []

        class SchemaSpyProvider(MockLLMProvider):
            def generate_structured(self, request, response_schema):
                recorded.append(response_schema)
                return super().generate_structured(request, response_schema)

        provider = SchemaSpyProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        findings = pipeline.run(synthetic_hdfc_input)

        assert len(recorded) == 1
        assert recorded[0] is ResearchFindingResponse, (
            f"Expected ResearchFindingResponse, got {recorded[0]}"
        )
        assert len(findings) > 0
        assert all(f.analyst == "financial_analyst" for f in findings)

    def test_pipeline_execution(self, synthetic_hdfc_input):
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        cost_tracker = CostTracker()

        pipeline = FinancialAnalystPipeline(
            provider=provider,
            cache=cache,
            cost_tracker=cost_tracker,
        )

        findings = pipeline.run(synthetic_hdfc_input)

        assert len(findings) > 0
        assert cost_tracker.total_calls == 1
        assert cost_tracker.total_cost_usd == 0.0

        for f in findings:
            assert f.analyst == "financial_analyst"
            assert len(f.evidence_ids) > 0
            assert 0.0 <= f.confidence <= 1.0

    def test_pipeline_cache_hit(self, synthetic_hdfc_input):
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        cost_tracker = CostTracker()

        pipeline = FinancialAnalystPipeline(
            provider=provider,
            cache=cache,
            cost_tracker=cost_tracker,
        )

        # First run -> cache miss
        pipeline.run(synthetic_hdfc_input)
        assert cost_tracker.total_calls == 1
        assert cost_tracker.total_cache_hits == 0

        # Second run -> cache hit
        pipeline.run(synthetic_hdfc_input)
        assert cost_tracker.total_calls == 2
        assert cost_tracker.total_cache_hits == 1
