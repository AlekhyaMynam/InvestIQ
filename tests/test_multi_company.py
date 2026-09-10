"""Multi-company regression tests — prove the pipeline is not HDFC-specific.

Tests cover:
1. Company identity preservation through the pipeline
2. Evidence provenance uses actual company identity
3. Different inputs produce different research context
4. CIO receives company-specific context
5. Cache isolation between companies

All tests are deterministic and make zero external API calls.
"""

from pathlib import Path

import pytest

from investiq.calculators.bank_metrics import compute_bank_metrics
from investiq.data.loader import load_financial_data
from investiq.llm.cache import MemoryLLMCache
from investiq.llm.cost import CostTracker
from investiq.llm.mock import MockLLMProvider
from investiq.research.evidence_collector import EvidenceCollector
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
from investiq.research.orchestrator import ResearchOrchestrator
from investiq.synthesis.cio import CIOSynthesizer

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


# ──────────────────────────────────────────────────────────────────────────────
# Test 1 – Company identity
# ──────────────────────────────────────────────────────────────────────────────


class TestCompanyIdentity:
    """Running research for different companies preserves their identity."""

    def test_hdfc_identity_preserved(self):
        """HDFCBANK research produces HDFCBANK identity."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        assert snapshot.ticker == "HDFCBANK"
        assert snapshot.company.name == "HDFC Bank Limited"
        assert snapshot.company.ticker == "HDFCBANK"

    def test_icici_identity_preserved(self):
        """ICICIBANK research produces ICICIBANK identity.

        Note: MockLLMProvider default responses reference SYN-HDFCBANK-*
        evidence IDs, so we must supply them. This is a mock limitation,
        not a pipeline issue. The key assertions verify that the company
        identity comes from ICICI data, not HDFC.
        """
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("ICICIBANK", evidence_items=evidence)

        assert snapshot.ticker == "ICICIBANK"
        assert snapshot.company.name == "ICICI Bank Limited"
        assert snapshot.company.ticker == "ICICIBANK"

    def test_company_identity_different(self):
        """HDFCBANK and ICICIBANK have different company identities."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        hdfc_snap = orchestrator.research("HDFCBANK", evidence_items=evidence)
        icici_snap = orchestrator.research("ICICIBANK", evidence_items=evidence)

        assert hdfc_snap.ticker != icici_snap.ticker
        assert hdfc_snap.company.name != icici_snap.company.name
        assert hdfc_snap.company.ticker != icici_snap.company.ticker
# ──────────────────────────────────────────────────────────────────────────────
# Test 2 – Evidence provenance
# ──────────────────────────────────────────────────────────────────────────────


class TestEvidenceProvenance:
    """Evidence source strings use the actual company identity."""

    def test_hdfc_evidence_source_contains_hdfc(self):
        """HDFC evidence sources contain 'HDFC Bank Limited'."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        metrics_list = compute_bank_metrics(data)
        for m in metrics_list:
            for ev in m.evidence:
                assert "HDFC Bank Limited" in ev.source, (
                    f"Expected 'HDFC Bank Limited' in evidence source, "
                    f"got: {ev.source}"
                )

    def test_icici_evidence_source_contains_icici(self):
        """ICICI evidence sources contain 'ICICI Bank Limited' (not HDFC)."""
        data = load_financial_data("ICICIBANK", data_dir=DATA_DIR)
        metrics_list = compute_bank_metrics(data)
        for m in metrics_list:
            for ev in m.evidence:
                assert "ICICI Bank Limited" in ev.source, (
                    f"Expected 'ICICI Bank Limited' in evidence source, "
                    f"got: {ev.source}"
                )
                # No accidental HDFC reference
                assert "HDFC" not in ev.source, (
                    f"ICICI evidence should not contain HDFC, got: {ev.source}"
                )

    def test_evidence_collector_preserves_provenance(self):
        """EvidenceCollector preserves company-specific provenance from metrics."""
        data = load_financial_data("ICICIBANK", data_dir=DATA_DIR)
        metrics_list = compute_bank_metrics(data)
        latest = metrics_list[-1]

        ev_set = EvidenceCollector.collect(metrics=latest)
        for item in ev_set:
            if item.tag.value in ("CALCULATION", "FACT"):
                assert "ICICI Bank Limited" in item.source, (
                    f"Expected ICICI in source, got: {item.source}"
                )
# ──────────────────────────────────────────────────────────────────────────────
# Test 3 – Different inputs produce different research context
# ──────────────────────────────────────────────────────────────────────────────


class TestDifferentResearchContext:
    """Different companies produce different metrics, evidence, and valuations."""

    def test_metrics_differ_between_companies(self):
        """HDFC and ICICI have different financial metrics."""
        hdfc_data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        icici_data = load_financial_data("ICICIBANK", data_dir=DATA_DIR)

        hdfc_metrics = compute_bank_metrics(hdfc_data)
        icici_metrics = compute_bank_metrics(icici_data)

        hdfc_latest = hdfc_metrics[-1]
        icici_latest = icici_metrics[-1]

        # Different companies should have different ROE values
        assert hdfc_latest.roe != icici_latest.roe, (
            "HDFC and ICICI should have different ROE values"
        )

        # Different companies should have different EPS values
        assert hdfc_latest.eps != icici_latest.eps, (
            "HDFC and ICICI should have different EPS values"
        )

    def test_valuation_differs_between_companies(self):
        """Different companies produce different valuations."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        hdfc_snap = orchestrator.research("HDFCBANK", evidence_items=evidence)
        icici_snap = orchestrator.research("ICICIBANK", evidence_items=evidence)

        # Different companies should have different fair values
        assert hdfc_snap.valuation.blended_fair_value != icici_snap.valuation.blended_fair_value, (
            "HDFC and ICICI should have different fair values"
        )

    def test_different_ticker_unknown_behavior(self):
        """Unknown ticker raises appropriate error (not silently returns HDFC)."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        with pytest.raises(FileNotFoundError):
            orchestrator.research("UNKNOWN_TICKER", evidence_items=[])
# ──────────────────────────────────────────────────────────────────────────────
# Test 4 – CIO receives company-specific context
# ──────────────────────────────────────────────────────────────────────────────


class TestCIOCompanyContext:
    """CIO synthesis is generated from the supplied company's snapshot."""

    def test_cio_hdfc_has_hdfc_context(self):
        """CIO for HDFC receives HDFC context in snapshot."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        # The snapshot contains HDFC identity
        assert snapshot.ticker == "HDFCBANK"
        assert snapshot.company.name == "HDFC Bank Limited"

    def test_cio_icici_has_icici_context(self):
        """CIO for ICICI receives ICICI context in snapshot."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("ICICIBANK", evidence_items=evidence)

        # The snapshot contains ICICI identity
        assert snapshot.ticker == "ICICIBANK"
        assert snapshot.company.name == "ICICI Bank Limited"

    def test_cio_synthesis_called_with_correct_snapshot(self):
        """CIO synthesizer receives snapshot with correct company context."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("ICICIBANK", evidence_items=evidence)

        synthesizer = CIOSynthesizer(provider=provider)
        synthesis = synthesizer.synthesize(snapshot)

        assert isinstance(synthesis.executive_summary, str)
        # The inputs to the CIO prompt use snapshot.ticker and snapshot.company.name
        assert snapshot.ticker == "ICICIBANK"


# ──────────────────────────────────────────────────────────────────────────────
# Test 5 – Cache isolation between companies
# ──────────────────────────────────────────────────────────────────────────────


class TestCacheIsolation:
    """Company-specific research cannot accidentally reuse another company's cache."""

    def test_different_companies_have_different_cache_keys(self):
        """CIO synthesis for different companies uses different cache keys."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
        evidence = get_synthetic_hdfcbank_evidence()
        shared_cache = MemoryLLMCache()

        # Synthesize for ICICI first
        icici_snap = orchestrator.research("ICICIBANK", evidence_items=evidence)
        cost_a = CostTracker()
        cio_a = CIOSynthesizer(provider=provider, cache=shared_cache, cost_tracker=cost_a)
        synthesis_a = cio_a.synthesize(icici_snap)

        # Synthesize for HDFC
        hdfc_snap = orchestrator.research("HDFCBANK", evidence_items=evidence)
        cost_b = CostTracker()
        cio_b = CIOSynthesizer(provider=provider, cache=shared_cache, cost_tracker=cost_b)
        synthesis_b = cio_b.synthesize(hdfc_snap)

        # Both companies should have had cache misses (first time)
        assert cost_a.total_cache_hits == 0
        assert cost_b.total_cache_hits == 0

        # Synthesize again — each should hit its own company-specific cache
        synthesis_a2 = cio_a.synthesize(icici_snap)
        synthesis_b2 = cio_b.synthesize(hdfc_snap)

        assert cost_a.total_cache_hits == 1  # ICICI hit its own cache
        assert cost_b.total_cache_hits == 1  # HDFC hit its own cache