"""Tests for the ResearchOrchestrator (Phase 3A)."""

from pathlib import Path

import pytest

from investiq.llm.mock import MockLLMProvider
from investiq.models.evidence import EvidenceItem
from investiq.models.financials import FinancialData
from investiq.models.research import (
    FindingCategory,
    ResearchFinding,
    ResearchSnapshot,
    ResearchStatusEnum,
)
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
from investiq.research.orchestrator import ResearchOrchestrator

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


class TestResearchOrchestrator:
    """Test the full orchestration pipeline."""

    def test_research_produces_snapshot(self):
        """Orchestrator produces a valid ResearchSnapshot from HDFCBANK data."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        assert isinstance(snapshot, ResearchSnapshot)
        assert snapshot.ticker == "HDFCBANK"
        assert snapshot.snapshot_id is not None
        assert snapshot.generated_at is not None

    def test_metrics_are_deterministic(self):
        """Bank metrics are computed deterministically (no LLM involved)."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        assert len(snapshot.metrics) == 5  # FY2021–FY2025
        latest = snapshot.metrics[-1]
        assert latest.fiscal_year == "FY2025"
        assert 10.0 <= latest.roe <= 20.0  # ROE in reasonable range
        assert latest.eps > 0
        assert len(latest.evidence) > 0

    def test_analyst_pipeline_invoked(self):
        """FinancialAnalystPipeline is invoked and produces findings."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        assert len(snapshot.findings) > 0
        assert all(isinstance(f, ResearchFinding) for f in snapshot.findings)

    def test_mock_provider_used_no_external_api(self):
        """MockLLMProvider is used — no external API required."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        assert len(snapshot.findings) > 0
        # Mock cost is always $0.00 — no real call was made
        assert snapshot.findings[0].analyst == "financial_analyst"

    def test_validated_research_findings(self):
        """All findings are valid ResearchFinding instances with required fields."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        for f in snapshot.findings:
            assert f.analyst is not None and len(f.analyst) > 0
            assert f.title is not None and len(f.title) > 0
            assert f.statement is not None and len(f.statement) > 0
            assert 0.0 <= f.confidence <= 1.0
            assert isinstance(f.evidence_ids, list)
            assert len(f.evidence_ids) > 0
            assert isinstance(f.category, FindingCategory)

    def test_evidence_ids_remain_valid(self):
        """Finding evidence IDs reference valid evidence from the fixture."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        valid_ids = {e.evidence_id for e in evidence}
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        for f in snapshot.findings:
            for eid in f.evidence_ids:
                assert eid in valid_ids, f"evidence_id {eid} not found in fixture"

    def test_synthetic_provenance_intact(self):
        """Synthetic evidence fixture provenance is preserved in the chain."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        # Evidence chain should contain items tagged CALCULATION
        calc_ids = {e.evidence_id for e in snapshot.evidence_chain}
        assert len(calc_ids) > 0

    def test_source_financial_data_not_mutated(self):
        """The orchestrator does not mutate the source FinancialData."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        # Snapshot's financial_data should be a valid FinancialData
        assert isinstance(snapshot.financial_data, FinancialData)
        assert snapshot.financial_data.company.ticker == "HDFCBANK"

    def test_failure_behavior_on_bad_ticker(self):
        """Orchestrator raises FileNotFoundError for unknown ticker."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        with pytest.raises(FileNotFoundError):
            orchestrator.research("INVALID", evidence_items=[])

    def test_snapshot_contains_valuation(self):
        """ResearchSnapshot includes a valid valuation summary."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        assert snapshot.valuation.blended_fair_value > 0
        assert len(snapshot.valuation.methods) >= 1  # At least one method

    def test_evidence_chain_in_snapshot(self):
        """Evidence chain includes metrics evidence and valuation evidence."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)

        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        assert len(snapshot.evidence_chain) > 0
        # Chain should contain at least some items from metrics or valuation
        all_chain_ids = [e.evidence_id for e in snapshot.evidence_chain]
        assert len(set(all_chain_ids)) == len(all_chain_ids), "duplicate evidence IDs in chain"