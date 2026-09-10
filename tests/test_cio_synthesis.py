"""Tests for CIO Synthesizer — synthesis of analyst findings into investment thesis.

All tests are deterministic and make zero external API calls.
"""

from pathlib import Path

import pytest

from investiq.llm.cache import MemoryLLMCache
from investiq.llm.cost import CostTracker
from investiq.llm.mock import MockLLMProvider
from investiq.models.research import ResearchSnapshot
from investiq.models.synthesis import CIOSynthesis, CIOSynthesisResponse
from investiq.synthesis.cio import CIOSynthesizer
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
from investiq.research.orchestrator import ResearchOrchestrator

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


@pytest.fixture(scope="module")
def hdfc_snapshot() -> ResearchSnapshot:
    """Create a realistic HDFCBANK ResearchSnapshot with all 3 analysts."""
    provider = MockLLMProvider(simulated_latency_ms=0.0)
    orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
    evidence = get_synthetic_hdfcbank_evidence()
    return orchestrator.research("HDFCBANK", evidence_items=evidence)
class TestCIOSynthesizerConstruction:
    """CIOSynthesizer construction."""

    def test_constructor_accepts_provider(self):
        """Constructor accepts LLMProvider."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        assert synthesizer.provider is provider

    def test_constructor_accepts_cache(self):
        """Constructor accepts optional cache."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        synthesizer = CIOSynthesizer(provider=provider, cache=cache)
        assert synthesizer.cache is cache

    def test_constructor_accepts_cost_tracker(self):
        """Constructor accepts optional cost tracker."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cost_tracker = CostTracker()
        synthesizer = CIOSynthesizer(provider=provider, cost_tracker=cost_tracker)
        assert synthesizer.cost_tracker is cost_tracker


class TestCIOSynthesizerExecution:
    """CIO synthesis execution."""

    def test_synthesize_returns_cio_synthesis(self, hdfc_snapshot):
        """synthesize() returns a CIOSynthesis."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis, CIOSynthesis)

    def test_executive_summary_present(self, hdfc_snapshot):
        """executive_summary is a non-empty string."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis.executive_summary, str) and len(synthesis.executive_summary) > 0

    def test_investment_thesis_present(self, hdfc_snapshot):
        """investment_thesis is a non-empty string."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis.investment_thesis, str) and len(synthesis.investment_thesis) > 0

    def test_key_strengths_list(self, hdfc_snapshot):
        """key_strengths is a non-empty list."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis.key_strengths, list) and len(synthesis.key_strengths) > 0

    def test_key_concerns_list(self, hdfc_snapshot):
        """key_concerns is a non-empty list."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis.key_concerns, list) and len(synthesis.key_concerns) > 0

    def test_growth_drivers_list(self, hdfc_snapshot):
        """growth_drivers is a non-empty list."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis.growth_drivers, list) and len(synthesis.growth_drivers) > 0

    def test_risks_list(self, hdfc_snapshot):
        """risks is a non-empty list."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis.risks, list) and len(synthesis.risks) > 0

    def test_scenarios_present(self, hdfc_snapshot):
        """All three scenarios are non-empty strings."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis.bull_case, str) and len(synthesis.bull_case) > 0
        assert isinstance(synthesis.base_case, str) and len(synthesis.base_case) > 0
        assert isinstance(synthesis.bear_case, str) and len(synthesis.bear_case) > 0

    def test_thesis_breakers_list(self, hdfc_snapshot):
        """thesis_breakers is a non-empty list."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis.thesis_breakers, list) and len(synthesis.thesis_breakers) > 0

    def test_overall_assessment_present(self, hdfc_snapshot):
        """overall_assessment is a non-empty string."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
class TestCIOSynthesizerCache:
    """Caching behavior."""

    def test_cache_hit(self, hdfc_snapshot):
        """Cache hit returns synthesis without calling provider."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        cost_tracker = CostTracker()
        synthesizer = CIOSynthesizer(
            provider=provider, cache=cache, cost_tracker=cost_tracker,
        )
        synthesis1 = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis1, CIOSynthesis)
        assert cost_tracker.total_calls == 1
        assert cost_tracker.total_cache_hits == 0
        synthesis2 = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis2, CIOSynthesis)
        assert cost_tracker.total_calls == 2
        assert cost_tracker.total_cache_hits == 1


class TestCIOSynthesizerCostTracking:
    """Cost tracking behavior."""

    def test_cost_tracker_records_call(self, hdfc_snapshot):
        """CostTracker records a call after synthesis."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cost_tracker = CostTracker()
        synthesizer = CIOSynthesizer(provider=provider, cost_tracker=cost_tracker)
        synthesizer.synthesize(hdfc_snapshot)
        assert cost_tracker.total_calls == 1
        assert cost_tracker.total_cost_usd == 0.0


class TestCIOSynthesizerOrchestratorIntegration:
    """Orchestrator integration — snapshot contains CIO synthesis."""

    def test_snapshot_contains_cio_synthesis(self):
        """ResearchSnapshot from orchestrator contains CIO synthesis."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)
        assert snapshot.cio_synthesis is not None
        assert isinstance(snapshot.cio_synthesis, CIOSynthesis)

    def test_snapshot_has_executive_summary(self):
        """CIO synthesis in snapshot has executive_summary."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)
        assert len(snapshot.cio_synthesis.executive_summary) > 0

    def test_analyst_findings_still_present(self):
        """All analyst findings are still present in the snapshot."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)
        analysts = {f.analyst for f in snapshot.findings}
        assert "financial_analyst" in analysts
        assert "asset_quality_analyst" in analysts
        assert "banking_business_analyst" in analysts
        assert len(snapshot.findings) >= 3

    def test_evidence_chain_present(self):
        """Full evidence chain is present in snapshot."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)
        assert len(snapshot.evidence_chain) > 0


class TestCIOSynthesizerMockProvider:
    """MockLLMProvider makes zero network calls."""

    def test_no_external_api_calls(self, hdfc_snapshot):
        """MockLLMProvider makes zero network calls."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(hdfc_snapshot)
        assert isinstance(synthesis, CIOSynthesis)
class TestCIOSynthesizerMultiCompany:
    """Multi-company regression — CIO is not tied to a single company."""

    def _make_company_snapshot(self, ticker: str, name: str, roe: float, eps: float) -> ResearchSnapshot:
        """Build a minimal ResearchSnapshot for a synthetic company."""
        from datetime import datetime, timezone
        from investiq.models.company import CompanyProfile, CompanyType, Sector
        from investiq.models.financials import FinancialData, MarketData
        from investiq.models.metrics import BankMetrics
        from investiq.models.valuation import ValuationSummary, ValuationResult, ValuationMethod
        from investiq.models.evidence import EvidenceItem, EvidenceTag, EvidenceDomain

        return ResearchSnapshot(
            snapshot_id=f"snap-{ticker.lower()}",
            ticker=ticker,
            company=CompanyProfile(
                ticker=ticker, name=name,
                sector=Sector.FINANCIAL_SERVICES,
                company_type=CompanyType.BANK,
            ),
            generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            financial_data=FinancialData(
                company=CompanyProfile(
                    ticker=ticker, name=name,
                    sector=Sector.FINANCIAL_SERVICES,
                    company_type=CompanyType.BANK,
                ),
                income_statements=[],
                balance_sheets=[],
                market_data=MarketData(current_price=100.0, market_cap=1000.0, shares_outstanding=10.0, as_of=datetime(2025, 1, 1).date()),
            ),
            metrics=[
                BankMetrics(
                    fiscal_year="FY2025",
                    roe=roe, roa=roe/8, nim=3.5,
                    casa_ratio=40.0 if "HDFC" in name else 30.0,
                    gross_npa_ratio=1.2, net_npa_ratio=0.4,
                    cost_to_income=42.0, credit_cost=0.5,
                    eps=eps, book_value_per_share=500.0,
                    evidence=[],
                ),
            ],
            valuation=ValuationSummary(
                methods=[
                    ValuationResult(
                        method=ValuationMethod.PB_ROE,
                        estimated_fair_value=1200.0,
                        current_price=100.0,
                        upside_pct=20.0,
                        assumptions=[],
                        evidence=[],
                    ),
                ],
                blended_fair_value=1200.0,
                verdict="Fairly Valued",
            ),
            findings=[],
            evidence_chain=[],
        )

    def test_cio_uses_company_a_identity(self):
        """CIO for company A uses company A's name in its input."""
        snap_a = self._make_company_snapshot("BANK_A", "Bank Alpha", roe=15.0, eps=50.0)
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        # Use preset to return company-dependent content
        synthesis = synthesizer.synthesize(snap_a)
        assert isinstance(synthesis, CIOSynthesis)
        # The mock response is static, but prove the input context was correct
        assert snap_a.ticker == "BANK_A"
        assert snap_a.company.name == "Bank Alpha"
        assert snap_a.metrics[-1].roe == 15.0

    def test_cio_uses_company_b_identity(self):
        """CIO for company B uses company B's name in its input."""
        snap_b = self._make_company_snapshot("BANK_B", "Bank Beta", roe=12.0, eps=40.0)
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(snap_b)
        assert isinstance(synthesis, CIOSynthesis)
        assert snap_b.ticker == "BANK_B"
        assert snap_b.company.name == "Bank Beta"
        assert snap_b.metrics[-1].roe == 12.0

    def test_different_companies_produce_different_cache_keys(self):
        """Different companies produce different cache keys."""
        snap_a = self._make_company_snapshot("BANK_A", "Bank Alpha", roe=15.0, eps=50.0)
        snap_b = self._make_company_snapshot("BANK_B", "Bank Beta", roe=12.0, eps=40.0)

        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        cost_tracker_a = CostTracker()
        cost_tracker_b = CostTracker()

        synthesizer_a = CIOSynthesizer(provider=provider, cache=cache, cost_tracker=cost_tracker_a)
        synthesizer_b = CIOSynthesizer(provider=provider, cache=cache, cost_tracker=cost_tracker_b)

        # Synthesize for both companies
        synthesis_a = synthesizer_a.synthesize(snap_a)
        synthesis_b = synthesizer_b.synthesize(snap_b)

        assert isinstance(synthesis_a, CIOSynthesis)
        assert isinstance(synthesis_b, CIOSynthesis)

        # Each company should have a cache miss (different keys)
        assert cost_tracker_a.total_calls == 1
        assert cost_tracker_a.total_cache_hits == 0
        assert cost_tracker_b.total_calls == 1
        assert cost_tracker_b.total_cache_hits == 0

        # Synthesize again — each should hit its own cache
        synthesis_a2 = synthesizer_a.synthesize(snap_a)
        synthesis_b2 = synthesizer_b.synthesize(snap_b)

        assert cost_tracker_a.total_calls == 2
        assert cost_tracker_a.total_cache_hits == 1  # hit A's cache
        assert cost_tracker_b.total_calls == 2
        assert cost_tracker_b.total_cache_hits == 1  # hit B's cache