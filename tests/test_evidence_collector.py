"""Tests for EvidenceCollector — combining supplied, metrics, and valuation evidence.

All tests are deterministic and make zero external API calls.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from investiq.calculators.bank_metrics import compute_bank_metrics
from investiq.calculators.bank_valuation import compute_bank_valuation
from investiq.data.loader import load_financial_data
from investiq.models.evidence import EvidenceItem, EvidenceTag
from investiq.research.evidence import EvidenceConflictError
from investiq.research.evidence_collector import EvidenceCollector
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


def _make_item(
    evidence_id: str,
    tag: EvidenceTag = EvidenceTag.FACT,
    label: str = "Test Evidence",
    source: str = "Test Source",
    source_field: str | None = None,
    value: float = 42.0,
) -> EvidenceItem:
    """Helper to create EvidenceItem instances for tests."""
    return EvidenceItem(
        evidence_id=evidence_id,
        tag=tag,
        label=label,
        source=source,
        source_field=source_field,
        timestamp=datetime.now(timezone.utc),
        value=value,
    )


@pytest.fixture(scope="module")
def hdfc_data():
    """Load HDFCBANK financial data once per module."""
    return load_financial_data("HDFCBANK", data_dir=DATA_DIR)


@pytest.fixture(scope="module")
def hdfc_latest_metrics(hdfc_data):
    """Compute and return FY2025 BankMetrics."""
    metrics_list = compute_bank_metrics(hdfc_data)
    return metrics_list[-1]


@pytest.fixture(scope="module")
def hdfc_valuation(hdfc_data, hdfc_latest_metrics):
    """Compute valuation summary for HDFCBANK."""
    latest_income = hdfc_data.income_statements[-1]
    return compute_bank_valuation(
        latest_metrics=hdfc_latest_metrics,
        current_price=hdfc_data.market_data.current_price,
        dividend_per_share=latest_income.dividend_per_share,
    )


class TestEvidenceCollectorCombination:
    """Collector combines evidence from multiple sources."""

    def test_supplied_evidence_only(self):
        """Collector works with only supplied evidence."""
        supplied = [
            _make_item("SUPPLIED-001"),
            _make_item("SUPPLIED-002"),
        ]
        ev_set = EvidenceCollector.collect(supplied_evidence=supplied)
        assert len(ev_set) == 2
        assert "SUPPLIED-001" in ev_set
        assert "SUPPLIED-002" in ev_set

    def test_metrics_evidence_only(self, hdfc_latest_metrics):
        """Collector works with only metrics evidence."""
        ev_set = EvidenceCollector.collect(metrics=hdfc_latest_metrics)
        assert len(ev_set) > 0
        for item in ev_set:
            assert item.tag == EvidenceTag.CALCULATION

    def test_valuation_evidence_only(self, hdfc_valuation):
        """Collector works with only valuation evidence."""
        ev_set = EvidenceCollector.collect(valuation=hdfc_valuation)
        assert len(ev_set) > 0
        tags = {item.tag for item in ev_set}
        assert EvidenceTag.CALCULATION in tags
        assert EvidenceTag.ASSUMPTION in tags

    def test_combines_all_sources(self, hdfc_latest_metrics, hdfc_valuation):
        """Collector combines supplied + metrics + valuation evidence."""
        supplied = get_synthetic_hdfcbank_evidence()
        ev_set = EvidenceCollector.collect(
            supplied_evidence=supplied,
            metrics=hdfc_latest_metrics,
            valuation=hdfc_valuation,
        )
        assert len(ev_set) > len(supplied)
        assert len(ev_set) > len(hdfc_latest_metrics.evidence)
        assert "SYN-HDFCBANK-ROE-001" in ev_set
class TestEvidenceCollectorDeduplication:
    """Collector deduplicates evidence from different sources."""

    def test_no_duplicates_when_sources_overlap(self, hdfc_latest_metrics, hdfc_valuation):
        """When sources overlap, IDs are still unique after dedup."""
        supplied = get_synthetic_hdfcbank_evidence()
        ev_set = EvidenceCollector.collect(
            supplied_evidence=supplied,
            metrics=hdfc_latest_metrics,
            valuation=hdfc_valuation,
        )
        ids = [item.evidence_id for item in ev_set]
        assert len(ids) == len(set(ids)), "evidence IDs must be unique"

    def test_identical_supplied_and_metrics_deduplicated(self, hdfc_latest_metrics):
        """Same ID+content from supplied and metrics = one copy kept."""
        first_metric_id = hdfc_latest_metrics.evidence[0].evidence_id
        dup_item = hdfc_latest_metrics.evidence[0]
        ev_set = EvidenceCollector.collect(
            supplied_evidence=[dup_item],
            metrics=hdfc_latest_metrics,
        )
        assert len(ev_set) == len(hdfc_latest_metrics.evidence)
        assert first_metric_id in ev_set

    def test_conflicting_supplied_and_metrics_raises_error(
        self, hdfc_latest_metrics):
        """Same ID, different content across sources raises error."""
        conflicting = _make_item(
            hdfc_latest_metrics.evidence[0].evidence_id,
            value=9999.9,
        )
        with pytest.raises(EvidenceConflictError):
            EvidenceCollector.collect(
                supplied_evidence=[conflicting],
                metrics=hdfc_latest_metrics,
            )


class TestEvidenceCollectorProvenance:
    """Provenance preservation through the collector."""

    def test_synthetic_evidence_remains_synthetic(
        self, hdfc_latest_metrics, hdfc_valuation):
        """Synthetic fixture evidence retains its source metadata."""
        supplied = get_synthetic_hdfcbank_evidence()
        ev_set = EvidenceCollector.collect(
            supplied_evidence=supplied,
            metrics=hdfc_latest_metrics,
            valuation=hdfc_valuation,
        )
        for syn_id in ["SYN-HDFCBANK-ROE-001", "SYN-HDFCBANK-NIM-001"]:
            item = ev_set.get(syn_id)
            assert item is not None
            assert "Synthetic" in item.source

    def test_source_not_mutated(self, hdfc_latest_metrics, hdfc_valuation):
        """Collector does not mutate source evidence objects."""
        supplied = get_synthetic_hdfcbank_evidence()
        original_ids = [e.evidence_id for e in supplied]
        original_values = [e.value for e in supplied]

        _ = EvidenceCollector.collect(
            supplied_evidence=supplied,
            metrics=hdfc_latest_metrics,
            valuation=hdfc_valuation,
        )
        assert [e.evidence_id for e in supplied] == original_ids
        assert [e.value for e in supplied] == original_values


class TestEvidenceCollectorEmptyInputs:
    """Collector handles empty/null inputs predictably."""

    def test_all_none(self):
        """All None inputs produce empty EvidenceSet."""
        ev_set = EvidenceCollector.collect()
        assert len(ev_set) == 0

    def test_all_empty(self):
        """All empty lists produce empty EvidenceSet."""
        ev_set = EvidenceCollector.collect(
            supplied_evidence=[],
            metrics=None,
            valuation=None,
        )
        assert len(ev_set) == 0

    def test_empty_supplied_metrics_only(self, hdfc_latest_metrics):
        """Empty supplied list with metrics works normally."""
        ev_set = EvidenceCollector.collect(
            supplied_evidence=[],
            metrics=hdfc_latest_metrics,
        )
        assert len(ev_set) > 0


class TestEvidenceCollectorOrdering:
    """Deterministic ordering is preserved."""

    def test_supplied_before_metrics_before_valuation(
        self, hdfc_latest_metrics, hdfc_valuation):
        """Supplied, then metrics, then valuation order is preserved."""
        supplied = get_synthetic_hdfcbank_evidence()
        supplied_ids = {e.evidence_id for e in supplied}

        ev_set = EvidenceCollector.collect(
            supplied_evidence=supplied,
            metrics=hdfc_latest_metrics,
            valuation=hdfc_valuation,
        )
        result = ev_set.to_list()

        max_supplied_idx = max(
            i for i, item in enumerate(result)
            if item.evidence_id in supplied_ids
        )
        for item in result:
            if item.evidence_id not in supplied_ids:
                nsidx = next(i for i, e in enumerate(result)
                             if e.evidence_id == item.evidence_id)
                assert nsidx >= max_supplied_idx, (
                    f"{item.evidence_id} should appear after all supplied items"
                )

    def test_repeatable_same_order(
        self, hdfc_latest_metrics, hdfc_valuation):
        """Multiple calls with same inputs produce same order."""
        supplied = get_synthetic_hdfcbank_evidence()
        ev_set1 = EvidenceCollector.collect(
            supplied_evidence=supplied,
            metrics=hdfc_latest_metrics,
            valuation=hdfc_valuation,
        )
        ev_set2 = EvidenceCollector.collect(
            supplied_evidence=supplied,
            metrics=hdfc_latest_metrics,
            valuation=hdfc_valuation,
        )
        ids1 = [e.evidence_id for e in ev_set1]
        ids2 = [e.evidence_id for e in ev_set2]
        assert ids1 == ids2