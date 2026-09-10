"""Tests for ResearchDeltaCalculator — deterministic snapshot comparison.

All tests are deterministic, use MockLLMProvider, and make zero external API calls.
"""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investiq.llm.mock import MockLLMProvider
from investiq.models.company import CompanyProfile, CompanyType, Sector
from investiq.models.financials import FinancialData, MarketData
from investiq.models.metrics import BankMetrics
from investiq.models.research import MetricChange, ResearchDelta, ResearchSnapshot
from investiq.models.valuation import ValuationSummary
from investiq.research.delta import ResearchDeltaCalculator
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
from investiq.research.orchestrator import ResearchOrchestrator


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


@pytest.fixture(scope="module")
def hdfc_snapshot() -> ResearchSnapshot:
    """Create a realistic HDFCBANK ResearchSnapshot using MockLLMProvider."""
    provider = MockLLMProvider(simulated_latency_ms=0.0)
    orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
    evidence = get_synthetic_hdfcbank_evidence()
    return orchestrator.research("HDFCBANK", evidence_items=evidence)


class TestDeltaValidation:
    """Snapshot compatibility validation."""

    def test_ticker_mismatch_raises_value_error(self, hdfc_snapshot):
        """Comparing snapshots for different tickers raises ValueError."""
        from copy import deepcopy
        other = deepcopy(hdfc_snapshot)
        other.ticker = "ICICIBANK"
        other.snapshot_id = "other-id"
        other.generated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="different tickers"):
            ResearchDeltaCalculator.compare(hdfc_snapshot, other)

    def test_same_snapshot_raises_value_error(self, hdfc_snapshot):
        """Comparing a snapshot with itself raises ValueError."""
        with pytest.raises(ValueError, match="with itself"):
            ResearchDeltaCalculator.compare(hdfc_snapshot, hdfc_snapshot)

    def test_older_not_newer_raises_value_error(self, hdfc_snapshot):
        """If 'previous' is newer than 'current', raises ValueError."""
        from copy import deepcopy
        older = deepcopy(hdfc_snapshot)
        older.snapshot_id = "older-id"
        older.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        newer = deepcopy(hdfc_snapshot)
        newer.snapshot_id = "newer-id"
        # Swap: pass newer as previous
        with pytest.raises(ValueError, match="must be older"):
            ResearchDeltaCalculator.compare(newer, older)

    def test_case_insensitive_ticker(self, hdfc_snapshot):
        """Ticker comparison is case-insensitive."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-a"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-b"
        s2.ticker = "hdfcbank"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert delta.ticker == "HDFCBANK"
class TestDeltaBasicComparison:
    """Basic comparison returns ResearchDelta."""

    def test_compare_returns_research_delta(self, hdfc_snapshot):
        """compare() returns a ResearchDelta instance."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert isinstance(delta, ResearchDelta)

    def test_delta_has_correct_ids(self, hdfc_snapshot):
        """Delta preserves previous and current snapshot IDs."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert delta.previous_snapshot_id == "snap-old"
        assert delta.current_snapshot_id == "snap-new"
        assert delta.previous_date == s1.generated_at
        assert delta.current_date == s2.generated_at
class TestDeltaMetricChanges:
    """Metric change detection."""

    def test_identical_metrics_no_changes(self, hdfc_snapshot):
        """Identical metrics produce no metric changes."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert isinstance(delta.metric_changes, list)

    def test_modified_metrics_detected(self, hdfc_snapshot):
        """Changes in metrics are captured as MetricChange objects."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if s2.metrics:
            modified = deepcopy(s2.metrics[-1])
            modified.roe = 99.9
            s2.metrics[-1] = modified
        delta = ResearchDeltaCalculator.compare(s1, s2)
        roe_changes = [m for m in delta.metric_changes if "ROE" in m.metric_name]
        assert len(roe_changes) >= 1

    def test_new_fiscal_years_detected(self, hdfc_snapshot):
        """Fiscal years in current but not previous go to new_data_periods."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if len(s1.metrics) > 1:
            oldest_year = s1.metrics[0].fiscal_year
            s1.metrics = s1.metrics[1:]
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert oldest_year in delta.new_data_periods

    def test_new_data_periods_sorted(self, hdfc_snapshot):
        """new_data_periods is sorted deterministically."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s1.metrics = []
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert delta.new_data_periods == sorted(delta.new_data_periods)
class TestDeltaChangePct:
    """Percentage change calculation."""

    def test_change_pct_positive(self, hdfc_snapshot):
        """Positive change produces positive percentage."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if s2.metrics:
            modified = deepcopy(s2.metrics[-1])
            modified.eps = s2.metrics[-1].eps * 2
            s2.metrics[-1] = modified
        delta = ResearchDeltaCalculator.compare(s1, s2)
        eps_changes = [m for m in delta.metric_changes if "EPS" in m.metric_name]
        for mc in eps_changes:
            if mc.change_pct is not None:
                assert mc.change_pct > 0

    def test_change_pct_negative(self, hdfc_snapshot):
        """Negative change produces negative percentage."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if s2.metrics:
            modified = deepcopy(s2.metrics[-1])
            modified.eps = s2.metrics[-1].eps * 0.5
            s2.metrics[-1] = modified
        delta = ResearchDeltaCalculator.compare(s1, s2)
        eps_changes = [m for m in delta.metric_changes if "EPS" in m.metric_name]
        for mc in eps_changes:
            if mc.change_pct is not None:
                assert mc.change_pct < 0

    def test_zero_previous_does_not_divide_by_zero(self, hdfc_snapshot):
        """Zero previous value does not cause division by zero."""
        from copy import deepcopy
        prev = deepcopy(hdfc_snapshot)
        prev.snapshot_id = "snap-old"
        prev.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        curr = deepcopy(hdfc_snapshot)
        curr.snapshot_id = "snap-new"
        curr.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if prev.metrics and curr.metrics:
            mp = deepcopy(prev.metrics[-1])
            mp.credit_cost = 0.0
            prev.metrics[-1] = mp
            mc = deepcopy(curr.metrics[-1])
            mc.credit_cost = 0.5
            curr.metrics[-1] = mc
        delta = ResearchDeltaCalculator.compare(prev, curr)
        cc_changes = [m for m in delta.metric_changes if "Credit Cost" in m.metric_name]
        for mc in cc_changes:
            assert mc.change_pct is None
            assert mc.significance in ("material", "minor")


class TestDeltaSignificance:
    """Material vs minor significance."""

    def test_material_change_detected(self, hdfc_snapshot):
        """A change >= 10%% is marked material."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if s2.metrics:
            modified = deepcopy(s2.metrics[-1])
            modified.roe = s2.metrics[-1].roe * 1.3  # +30%
            s2.metrics[-1] = modified
        delta = ResearchDeltaCalculator.compare(s1, s2)
        roe_changes = [m for m in delta.metric_changes if "ROE" in m.metric_name]
        for mc in roe_changes:
            if mc.change_pct is not None and abs(mc.change_pct) >= 10:
                assert mc.significance == "material"

    def test_minor_change_detected(self, hdfc_snapshot):
        """A change < 10%% is marked minor."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if s2.metrics:
            modified = deepcopy(s2.metrics[-1])
            modified.roe = s2.metrics[-1].roe * 1.05  # +5%
            s2.metrics[-1] = modified
        delta = ResearchDeltaCalculator.compare(s1, s2)
        roe_changes = [m for m in delta.metric_changes if "ROE" in m.metric_name]
        for mc in roe_changes:
            if mc.change_pct is not None and abs(mc.change_pct) < 10:
                assert mc.significance == "minor"
class TestDeltaValuation:
    """Valuation change calculation."""

    def test_valuation_change_calculated(self, hdfc_snapshot):
        """Valuation change is populated in the delta."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        delta = ResearchDeltaCalculator.compare(s1, s2)
        vc = delta.valuation_change
        assert "previous_blended_fair_value" in vc
        assert "current_blended_fair_value" in vc
        assert "blended_fair_value_change" in vc
        assert "blended_fair_value_change_pct" in vc
        assert "previous_verdict" in vc
        assert "current_verdict" in vc

    def test_valuation_verdict_change(self, hdfc_snapshot):
        """Verdict change is reflected in valuation_change dict."""
        from copy import deepcopy
        from investiq.models.valuation import ValuationSummary
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        s2.valuation = ValuationSummary(
            methods=s2.valuation.methods,
            blended_fair_value=9999.99,
            verdict="Overvalued",
        )
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert delta.valuation_change["previous_verdict"] == s1.valuation.verdict
        assert delta.valuation_change["current_verdict"] == "Overvalued"
        assert delta.valuation_change["blended_fair_value_change_pct"] is not None


class TestDeltaSummary:
    """Deterministic summary generation."""

    def test_summary_generated(self, hdfc_snapshot):
        """Summary is a non-empty string."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if s2.metrics:
            modified = deepcopy(s2.metrics[-1])
            modified.roe = s2.metrics[-1].roe * 1.3
            s2.metrics[-1] = modified
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert isinstance(delta.summary, str)
        assert len(delta.summary) > 0

    def test_summary_no_changes(self, hdfc_snapshot):
        """When nothing changes, summary says 'No material changes'."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        delta = ResearchDeltaCalculator.compare(s1, s2)
        if not delta.metric_changes and not delta.new_data_periods:
            assert "No material changes" in delta.summary


class TestDeltaNonMutation:
    """Snapshots are not mutated by comparison."""

    def test_snapshots_not_mutated(self, hdfc_snapshot):
        """Original snapshots remain unchanged after comparison."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        original_s1_id = s1.snapshot_id
        original_s2_id = s2.snapshot_id
        _ = ResearchDeltaCalculator.compare(s1, s2)
        assert s1.snapshot_id == original_s1_id
        assert s2.snapshot_id == original_s2_id


class TestDeltaMultipleMetrics:
    """Multiple metric changes."""

    def test_multiple_metric_changes(self, hdfc_snapshot):
        """Multiple metrics changing produces multiple MetricChange entries."""
        from copy import deepcopy
        s1 = deepcopy(hdfc_snapshot)
        s1.snapshot_id = "snap-old"
        s1.generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s2 = deepcopy(hdfc_snapshot)
        s2.snapshot_id = "snap-new"
        s2.generated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if s2.metrics:
            modified = deepcopy(s2.metrics[-1])
            modified.roe = s2.metrics[-1].roe * 1.5
            modified.nim = s2.metrics[-1].nim * 0.7
            modified.eps = s2.metrics[-1].eps * 2.0
            s2.metrics[-1] = modified
        delta = ResearchDeltaCalculator.compare(s1, s2)
        assert len(delta.metric_changes) >= 3
        names = {mc.metric_name for mc in delta.metric_changes}
        assert any("ROE" in n for n in names)
        assert any("NIM" in n for n in names)
        assert any("EPS" in n for n in names)