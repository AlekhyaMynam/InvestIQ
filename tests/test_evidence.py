"""Tests for EvidenceSet — deduplication, lookup, filtering, and provenance preservation.

All tests are deterministic and make zero external API calls.
"""

from datetime import date, datetime, timezone

import pytest

from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag
from investiq.research.evidence import (
    EvidenceConflictError,
    EvidenceSet,
    _content_key,
)


def _make_item(
    evidence_id: str,
    tag: EvidenceTag = EvidenceTag.FACT,
    label: str = "Test Evidence",
    source: str = "Test Source",
    source_field: str | None = None,
    value: float = 42.0,
    domain: EvidenceDomain | None = None,
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
        domain=domain,
    )


class TestEvidenceSetConstruction:
    """EvidenceSet can be constructed from various inputs."""

    def test_empty_construction(self):
        """An EvidenceSet can be created with no items."""
        ev_set = EvidenceSet()
        assert len(ev_set) == 0
        assert list(ev_set) == []

    def test_from_list(self):
        """An EvidenceSet can be created from a list of items."""
        items = [
            _make_item("ID-001"),
            _make_item("ID-002"),
        ]
        ev_set = EvidenceSet(evidence=items)
        assert len(ev_set) == 2

    def test_from_none(self):
        """Passing None to constructor produces an empty set."""
        ev_set = EvidenceSet(evidence=None)
        assert len(ev_set) == 0

    def test_evidence_ids_preserved(self):
        """evidence_id values from the source items are preserved exactly."""
        items = [
            _make_item("SYN-HDFCBANK-ROE-001"),
            _make_item("SYN-HDFCBANK-NIM-001"),
        ]
        ev_set = EvidenceSet(evidence=items)
        assert "SYN-HDFCBANK-ROE-001" in ev_set
        assert "SYN-HDFCBANK-NIM-001" in ev_set

    def test_to_list_returns_all_items(self):
        """to_list() returns all items in insertion order."""
        items = [
            _make_item("ID-A", value=10.0),
            _make_item("ID-B", value=20.0),
        ]
        ev_set = EvidenceSet(evidence=items)
        result = ev_set.to_list()
        assert len(result) == 2
        assert result[0].evidence_id == "ID-A"
        assert result[1].evidence_id == "ID-B"

class TestEvidenceSetDeduplication:
    """Deduplication by evidence_id."""

    def test_identical_duplicate_removed(self):
        """If the same evidence_id appears with identical content,
        only one copy is kept."""
        item = _make_item("ID-001", value=100.0)
        ev_set = EvidenceSet(evidence=[item, item])
        assert len(ev_set) == 1
        assert ev_set.get("ID-001") is not None
        assert ev_set.get("ID-001").value == 100.0

    def test_identical_duplicate_from_separate_add(self):
        """Adding an identical item via add() deduplicates."""
        item1 = _make_item("ID-001", value=100.0)
        item2 = _make_item("ID-001", value=100.0)
        ev_set = EvidenceSet(evidence=[item1])
        ev_set.add(item2)
        assert len(ev_set) == 1

    def test_conflicting_duplicate_raises_error(self):
        """If the same evidence_id appears with different content,
        EvidenceConflictError is raised."""
        item1 = _make_item("ID-001", value=100.0)
        item2 = _make_item("ID-001", value=200.0)
        with pytest.raises(EvidenceConflictError) as exc_info:
            EvidenceSet(evidence=[item1, item2])
        assert "ID-001" in str(exc_info.value)

    def test_conflicting_duplicate_on_add(self):
        """Adding a conflicting item via add() raises EvidenceConflictError."""
        item1 = _make_item("ID-001", value=100.0)
        item2 = _make_item("ID-001", value=200.0)
        ev_set = EvidenceSet(evidence=[item1])
        with pytest.raises(EvidenceConflictError):
            ev_set.add(item2)


class TestEvidenceSetLookup:
    """Lookup by evidence_id."""

    def test_get_existing(self):
        """get() returns the item for a valid evidence_id."""
        item = _make_item("ID-001")
        ev_set = EvidenceSet(evidence=[item])
        result = ev_set.get("ID-001")
        assert result is not None
        assert result.evidence_id == "ID-001"

    def test_get_missing(self):
        """get() returns None for an unknown evidence_id."""
        ev_set = EvidenceSet()
        assert ev_set.get("NONEXISTENT") is None

    def test_contains_existing(self):
        """'in' operator works for existing evidence_id."""
        ev_set = EvidenceSet(evidence=[_make_item("ID-001")])
        assert "ID-001" in ev_set

    def test_contains_missing(self):
        """'in' operator returns False for unknown evidence_id."""
        ev_set = EvidenceSet()
        assert "NONEXISTENT" not in ev_set


class TestEvidenceSetFiltering:
    """Filtering by tag, source, and source_field."""

    def test_filter_by_tag(self):
        """filter_by_tag returns only items with the matching tag."""
        items = [
            _make_item("ID-001", tag=EvidenceTag.FACT),
            _make_item("ID-002", tag=EvidenceTag.CALCULATION),
            _make_item("ID-003", tag=EvidenceTag.FACT),
        ]
        ev_set = EvidenceSet(evidence=items)
        facts = ev_set.filter_by_tag(EvidenceTag.FACT)
        assert len(facts) == 2
        assert all(it.tag == EvidenceTag.FACT for it in facts)

    def test_filter_by_tag_none(self):
        """filter_by_tag returns empty list when no items match."""
        items = [_make_item("ID-001", tag=EvidenceTag.FACT)]
        ev_set = EvidenceSet(evidence=items)
        result = ev_set.filter_by_tag(EvidenceTag.ASSUMPTION)
        assert result == []

    def test_filter_by_source(self):
        """filter_by_source returns items whose source contains the string."""
        items = [
            _make_item("ID-001", source="HDFC Bank Report"),
            _make_item("ID-002", source="ICICI Bank Report"),
        ]
        ev_set = EvidenceSet(evidence=items)
        hdfc_items = ev_set.filter_by_source("HDFC")
        assert len(hdfc_items) == 1
        assert hdfc_items[0].evidence_id == "ID-001"

    def test_filter_by_source_field(self):
        """filter_by_source_field returns items matching the field name."""
        items = [
            _make_item("ID-001", source_field="metrics.roe"),
            _make_item("ID-002", source_field="metrics.nim"),
            _make_item("ID-003", source_field="balance_sheet.total_equity"),
        ]
        ev_set = EvidenceSet(evidence=items)
        metrics_items = ev_set.filter_by_source_field("metrics.")
        assert len(metrics_items) == 2
class TestEvidenceSetProvenance:
    """Provenance preservation and synthetic evidence."""

    def test_synthetic_evidence_remains_synthetic(self):
        """Synthetic evidence fixtures retain their provenance through EvidenceSet."""
        items = [
            EvidenceItem(
                evidence_id="SYN-HDFCBANK-ROE-001",
                tag=EvidenceTag.CALCULATION,
                label="Return on Equity FY2025",
                source="InvestIQ Bank Metrics Calculator (Synthetic Fixture)",
                publication_date=date(2025, 4, 15),
                value=15.42,
            ),
            EvidenceItem(
                evidence_id="SYN-HDFCBANK-NIM-001",
                tag=EvidenceTag.CALCULATION,
                label="Net Interest Margin FY2025",
                source="InvestIQ Bank Metrics Calculator (Synthetic Fixture)",
                publication_date=date(2025, 4, 15),
                value=3.48,
            ),
        ]
        ev_set = EvidenceSet(evidence=items)
        roe = ev_set.get("SYN-HDFCBANK-ROE-001")
        assert roe is not None
        assert roe.evidence_id == "SYN-HDFCBANK-ROE-001"
        assert "Synthetic" in roe.source
        assert roe.value == 15.42
        nim = ev_set.get("SYN-HDFCBANK-NIM-001")
        assert nim is not None
        assert nim.value == 3.48

    def test_provenance_fields_preserved(self):
        """All provenance metadata fields survive round-trip through EvidenceSet."""
        item = EvidenceItem(
            evidence_id="TEST-PROV-001",
            tag=EvidenceTag.ASSUMPTION,
            label="Cost of Equity",
            source="InvestIQ Valuation Model",
            source_field="valuation.coe",
            source_url="https://investiq.internal/assumptions/coe",
            publication_date=date(2025, 1, 1),
            retrieved_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            value=0.135,
        )
        ev_set = EvidenceSet(evidence=[item])
        retrieved = ev_set.get("TEST-PROV-001")
        assert retrieved is not None
        assert retrieved.tag == EvidenceTag.ASSUMPTION
        assert retrieved.source == "InvestIQ Valuation Model"
        assert retrieved.source_field == "valuation.coe"
        assert retrieved.source_url == "https://investiq.internal/assumptions/coe"
        assert retrieved.publication_date == date(2025, 1, 1)
        assert retrieved.retrieved_at is not None
        assert retrieved.timestamp is not None
        assert retrieved.value == 0.135

    def test_evidence_not_converted_to_strings(self):
        """Evidence items remain typed EvidenceItem objects, not strings."""
        item = _make_item("ID-001", value=42.5)
        ev_set = EvidenceSet(evidence=[item])
        retrieved = ev_set.get("ID-001")
        assert isinstance(retrieved, EvidenceItem)
        assert isinstance(retrieved.value, float)


class TestEvidenceSetEdgeCases:
    """Edge cases and invalid inputs."""

    def test_empty_list(self):
        """EvidenceSet([]) produces an empty collection."""
        ev_set = EvidenceSet(evidence=[])
        assert len(ev_set) == 0

    def test_many_items(self):
        """EvidenceSet handles a large number of items."""
        items = [_make_item(f"ID-{i:04d}") for i in range(100)]
        ev_set = EvidenceSet(evidence=items)
        assert len(ev_set) == 100

    def test_iteration(self):
        """EvidenceSet is iterable."""
        items = [
            _make_item("ID-001"),
            _make_item("ID-002"),
        ]
        ev_set = EvidenceSet(evidence=items)
        ids = [item.evidence_id for item in ev_set]
        assert ids == ["ID-001", "ID-002"]

    def test_deterministic_ordering(self):
        """Items are preserved in insertion order."""
        items = [
            _make_item("ID-B"),
            _make_item("ID-A"),
            _make_item("ID-C"),
        ]
        ev_set = EvidenceSet(evidence=items)
        result = ev_set.to_list()
        assert [e.evidence_id for e in result] == ["ID-B", "ID-A", "ID-C"]


class TestEvidenceSetEdgeCasesAdd:
    """More edge cases for EvidenceSet."""

    def test_deterministic_ordering_after_add(self):
        """Adding items via add() appends to the end."""
        ev_set = EvidenceSet()
        ev_set.add(_make_item("ID-First"))
        ev_set.add(_make_item("ID-Second"))
        result = ev_set.to_list()
        assert result[0].evidence_id == "ID-First"
        assert result[1].evidence_id == "ID-Second"


class TestContentKey:
    """Unit tests for the _content_key helper."""

    def test_excludes_timestamp(self):
        """_content_key excludes 'timestamp' from the comparison key."""
        item = _make_item("ID-001", value=100.0)
        key = _content_key(item)
        assert "timestamp" not in key

    def test_excludes_retrieved_at(self):
        """_content_key excludes 'retrieved_at' from the comparison key."""
        item = _make_item("ID-001", value=100.0)
        key = _content_key(item)
        assert "retrieved_at" not in key

    def test_includes_other_fields(self):
        """_content_key includes key fields that define evidence content."""
        item = _make_item(
            "ID-001",
            tag=EvidenceTag.CALCULATION,
            label="ROE Test",
            source="Test Source",
            source_field="metrics.roe",
            value=15.5,
        )
        key = _content_key(item)
        assert key["evidence_id"] == "ID-001"
        assert key["tag"] == EvidenceTag.CALCULATION
        assert key["label"] == "ROE Test"
        assert key["source"] == "Test Source"
        assert key["source_field"] == "metrics.roe"


class TestSyntheticBankEvidence:
    """Tests for the ticker-aware synthetic evidence fixture."""

    def test_hdfcbank_evidence_has_hdfc_identity(self):
        """HDFCBANK evidence IDs contain HDFCBANK."""
        from investiq.research.evidence_fixture import get_synthetic_bank_evidence
        items = get_synthetic_bank_evidence("HDFCBANK")
        assert len(items) == 5
        for item in items:
            assert "HDFCBANK" in item.evidence_id
            assert not item.evidence_id.startswith("SYN-HDFC-")  # old format (note: SYN-HDFCBANK- is the new format)

    def test_icicibank_evidence_has_icici_identity(self):
        """ICICIBANK evidence IDs contain ICICIBANK, not HDFC."""
        from investiq.research.evidence_fixture import get_synthetic_bank_evidence
        items = get_synthetic_bank_evidence("ICICIBANK")
        assert len(items) == 5
        for item in items:
            assert "ICICIBANK" in item.evidence_id
            assert "HDFC" not in item.evidence_id

    def test_sbin_evidence_has_sbi_identity(self):
        """SBIN evidence IDs contain SBIN, not HDFC."""
        from investiq.research.evidence_fixture import get_synthetic_bank_evidence
        items = get_synthetic_bank_evidence("SBIN")
        assert len(items) == 5
        for item in items:
            assert "SBIN" in item.evidence_id
            assert "HDFC" not in item.evidence_id

    def test_ids_isolated_between_companies(self):
        """Different companies produce non-overlapping evidence ID sets."""
        from investiq.research.evidence_fixture import get_synthetic_bank_evidence
        hdfc = {i.evidence_id for i in get_synthetic_bank_evidence("HDFCBANK")}
        icici = {i.evidence_id for i in get_synthetic_bank_evidence("ICICIBANK")}
        sbi = {i.evidence_id for i in get_synthetic_bank_evidence("SBIN")}
        assert hdfc.isdisjoint(icici)
        assert hdfc.isdisjoint(sbi)
        assert icici.isdisjoint(sbi)

    def test_deterministic_for_same_ticker(self):
        """Same ticker produces identical evidence across calls."""
        from investiq.research.evidence_fixture import get_synthetic_bank_evidence
        first = get_synthetic_bank_evidence("HDFCBANK")
        second = get_synthetic_bank_evidence("HDFCBANK")
        for a, b in zip(first, second):
            assert a.evidence_id == b.evidence_id
            assert a.value == b.value

    def test_backward_compatible_wrapper(self):
        """get_synthetic_hdfcbank_evidence() still works."""
        from investiq.research.evidence_fixture import (
            get_synthetic_hdfcbank_evidence,
            get_synthetic_bank_evidence,
        )
        old = get_synthetic_hdfcbank_evidence()
        new = get_synthetic_bank_evidence("HDFCBANK")
        assert len(old) == len(new)
        for a, b in zip(old, new):
            assert a.evidence_id == b.evidence_id
            assert a.value == b.value

    def test_lowercase_ticker_normalized(self):
        """Lowercase ticker is normalized to uppercase."""
        from investiq.research.evidence_fixture import get_synthetic_bank_evidence
        items = get_synthetic_bank_evidence("hdfcbank")
        for item in items:
            assert "HDFCBANK" in item.evidence_id
class TestEvidenceSetDomainFiltering:
    """Domain filtering on EvidenceSet."""

    def test_filter_by_domain_financial(self):
        """filter_by_domain(FINANCIAL) returns only financial evidence."""
        items = [
            _make_item("FIN-001", domain=EvidenceDomain.FINANCIAL),
            _make_item("AQ-001", domain=EvidenceDomain.ASSET_QUALITY),
            _make_item("FIN-002", domain=EvidenceDomain.FINANCIAL),
        ]
        ev_set = EvidenceSet(evidence=items)
        result = ev_set.filter_by_domain(EvidenceDomain.FINANCIAL)
        assert len(result) == 2
        assert all(it.domain == EvidenceDomain.FINANCIAL for it in result)

    def test_filter_by_domain_asset_quality(self):
        """filter_by_domain(ASSET_QUALITY) returns only asset-quality evidence."""
        items = [
            _make_item("FIN-001", domain=EvidenceDomain.FINANCIAL),
            _make_item("AQ-001", domain=EvidenceDomain.ASSET_QUALITY),
        ]
        ev_set = EvidenceSet(evidence=items)
        result = ev_set.filter_by_domain(EvidenceDomain.ASSET_QUALITY)
        assert len(result) == 1
        assert result[0].evidence_id == "AQ-001"

    def test_filter_by_domain_none(self):
        """filter_by_domain returns empty list when no items match."""
        items = [_make_item("FIN-001", domain=EvidenceDomain.FINANCIAL)]
        ev_set = EvidenceSet(evidence=items)
        result = ev_set.filter_by_domain(EvidenceDomain.ASSET_QUALITY)
        assert result == []

    def test_filter_by_domain_preserves_ordering(self):
        """Domain filtering preserves deterministic ordering."""
        items = [
            _make_item("AQ-002", domain=EvidenceDomain.ASSET_QUALITY),
            _make_item("FIN-001", domain=EvidenceDomain.FINANCIAL),
            _make_item("AQ-001", domain=EvidenceDomain.ASSET_QUALITY),
        ]
        ev_set = EvidenceSet(evidence=items)
        result = ev_set.filter_by_domain(EvidenceDomain.ASSET_QUALITY)
        assert [e.evidence_id for e in result] == ["AQ-002", "AQ-001"]

    def test_filter_by_domain_no_mutation(self):
        """Domain filtering does not mutate the original EvidenceSet."""
        items = [
            _make_item("FIN-001", domain=EvidenceDomain.FINANCIAL),
            _make_item("AQ-001", domain=EvidenceDomain.ASSET_QUALITY),
        ]
        ev_set = EvidenceSet(evidence=items)
        _ = ev_set.filter_by_domain(EvidenceDomain.ASSET_QUALITY)
        assert len(ev_set) == 2  # unchanged

    def test_filter_by_domain_provenance_preserved(self):
        """Filtered items retain all original provenance fields."""
        item = EvidenceItem(
            evidence_id="AQ-001",
            tag=EvidenceTag.CALCULATION,
            label="Gross NPA Ratio",
            source="HDFC Bank Financial Statements FY2025",
            source_field="metrics.gross_npa_ratio",
            source_url="https://example.com",
            publication_date=date(2025, 4, 15),
            value=1.23,
            domain=EvidenceDomain.ASSET_QUALITY,
        )
        ev_set = EvidenceSet(evidence=[item])
        result = ev_set.filter_by_domain(EvidenceDomain.ASSET_QUALITY)
        assert len(result) == 1
        retrieved = result[0]
        assert retrieved.evidence_id == "AQ-001"
        assert retrieved.tag == EvidenceTag.CALCULATION
        assert retrieved.label == "Gross NPA Ratio"
        assert retrieved.source == "HDFC Bank Financial Statements FY2025"
        assert retrieved.source_field == "metrics.gross_npa_ratio"
        assert retrieved.source_url == "https://example.com"
        assert retrieved.publication_date == date(2025, 4, 15)
        assert retrieved.value == 1.23
        assert retrieved.domain == EvidenceDomain.ASSET_QUALITY

    def test_domain_default_is_none(self):
        """EvidenceItem without explicit domain has domain=None."""
        item = _make_item("NO-DOMAIN")
        assert item.domain is None

    def test_filter_by_domain_none_items(self):
        """Items with domain=None are not returned by filter_by_domain."""
        items = [
            _make_item("NO-DOMAIN"),
            _make_item("FIN-001", domain=EvidenceDomain.FINANCIAL),
        ]
        ev_set = EvidenceSet(evidence=items)
        result = ev_set.filter_by_domain(EvidenceDomain.FINANCIAL)
        assert len(result) == 1
        assert result[0].evidence_id == "FIN-001"

