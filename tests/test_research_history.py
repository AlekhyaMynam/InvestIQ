"""Tests for ResearchHistoryService — ticker-scoped history and delta orchestration.

All tests use tmp_path and make zero external API calls.
"""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from investiq.models.company import CompanyProfile, CompanyType, Sector
from investiq.models.financials import FinancialData, MarketData
from investiq.models.research import ResearchDelta, ResearchSnapshot
from investiq.models.valuation import ValuationSummary
from investiq.research.delta import ResearchDeltaCalculator
from investiq.research.history import ResearchHistoryService
from investiq.research.snapshot_store import ResearchSnapshotStore


def _make_snapshot(
    snapshot_id: str,
    ticker: str = "TEST",
    generated_at: datetime | None = None,
) -> ResearchSnapshot:
    """Create a minimal ResearchSnapshot for testing history mechanics."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    return ResearchSnapshot(
        snapshot_id=snapshot_id,
        ticker=ticker,
        company=CompanyProfile(
            ticker=ticker,
            name="Test Company",
            sector=Sector.FINANCIAL_SERVICES,
            company_type=CompanyType.BANK,
        ),
        generated_at=generated_at,
        financial_data=FinancialData(
            company=CompanyProfile(
                ticker=ticker,
                name="Test Company",
                sector=Sector.FINANCIAL_SERVICES,
                company_type=CompanyType.BANK,
            ),
            income_statements=[],
            balance_sheets=[],
            market_data=MarketData(
                current_price=100.0,
                market_cap=1000.0,
                shares_outstanding=10.0,
                as_of=date(2025, 1, 1),
            ),
        ),
        metrics=[],
        valuation=ValuationSummary(
            methods=[], blended_fair_value=0.0, verdict="Fairly Valued",
        ),
        findings=[],
        evidence_chain=[],
    )


@pytest.fixture
def store(tmp_path) -> ResearchSnapshotStore:
    """Create a ResearchSnapshotStore in a temporary directory."""
    return ResearchSnapshotStore(store_dir=tmp_path)


@pytest.fixture
def service(store) -> ResearchHistoryService:
    """Create a ResearchHistoryService backed by the temp store."""
    return ResearchHistoryService(store=store)


class TestEmptyHistory:
    """No snapshots in the store."""

    def test_list_empty(self, service):
        """list_for_ticker returns [] when no snapshots exist."""
        assert service.list_for_ticker("HDFCBANK") == []

    def test_get_latest_none(self, service):
        """get_latest returns None when no snapshots exist."""
        assert service.get_latest("HDFCBANK") is None

    def test_get_previous_none(self, service):
        """get_previous returns None when no snapshots exist."""
        assert service.get_previous("HDFCBANK") is None

    def test_compare_latest_none(self, service):
        """compare_latest returns None when no snapshots exist."""
        assert service.compare_latest("HDFCBANK") is None


class TestOneSnapshot:
    """Single snapshot in the store."""

    def test_list_one(self, store, service):
        """list_for_ticker returns the single snapshot."""
        snap = _make_snapshot("snap-1")
        store.save(snap)
        result = service.list_for_ticker("TEST")
        assert len(result) == 1
        assert result[0].snapshot_id == "snap-1"

    def test_get_latest_one(self, store, service):
        """get_latest returns the single snapshot."""
        snap = _make_snapshot("snap-1")
        store.save(snap)
        result = service.get_latest("TEST")
        assert result is not None
        assert result.snapshot_id == "snap-1"

    def test_get_previous_one(self, store, service):
        """get_previous returns None with only one snapshot."""
        store.save(_make_snapshot("snap-1"))
        assert service.get_previous("TEST") is None

    def test_compare_latest_one(self, store, service):
        """compare_latest returns None with only one snapshot."""
        store.save(_make_snapshot("snap-1"))
        assert service.compare_latest("TEST") is None


class TestTwoSnapshots:
    """Two snapshots for the same ticker."""

    def test_list_two(self, store, service):
        """list_for_ticker returns both in chronological order."""
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.save(_make_snapshot("snap-old", generated_at=t1))
        store.save(_make_snapshot("snap-new", generated_at=t2))
        result = service.list_for_ticker("TEST")
        assert len(result) == 2
        assert result[0].snapshot_id == "snap-old"
        assert result[1].snapshot_id == "snap-new"

    def test_get_latest_two(self, store, service):
        """get_latest returns the newer snapshot."""
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.save(_make_snapshot("snap-old", generated_at=t1))
        store.save(_make_snapshot("snap-new", generated_at=t2))
        result = service.get_latest("TEST")
        assert result is not None
        assert result.snapshot_id == "snap-new"

    def test_get_previous_two(self, store, service):
        """get_previous returns the older snapshot."""
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.save(_make_snapshot("snap-old", generated_at=t1))
        store.save(_make_snapshot("snap-new", generated_at=t2))
        result = service.get_previous("TEST")
        assert result is not None
        assert result.snapshot_id == "snap-old"

    def test_compare_latest_two(self, store, service):
        """compare_latest produces a ResearchDelta."""
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.save(_make_snapshot("snap-old", generated_at=t1))
        store.save(_make_snapshot("snap-new", generated_at=t2))
        delta = service.compare_latest("TEST")
        assert isinstance(delta, ResearchDelta)
        assert delta.previous_snapshot_id == "snap-old"
        assert delta.current_snapshot_id == "snap-new"
class TestMultipleSnapshots:
    """Multiple snapshots for the same ticker."""

    def test_chronological_ordering(self, store, service):
        """Snapshots are ordered oldest to newest."""
        times = [
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 6, 15, tzinfo=timezone.utc),
            datetime(2025, 3, 10, tzinfo=timezone.utc),
        ]
        for i, t in enumerate(times):
            store.save(_make_snapshot(f"snap-{i}", generated_at=t))
        result = service.list_for_ticker("TEST")
        assert [s.snapshot_id for s in result] == ["snap-0", "snap-1", "snap-2"]

    def test_get_latest_multiple(self, store, service):
        """get_latest returns the chronologically newest."""
        times = [
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 6, 15, tzinfo=timezone.utc),
            datetime(2025, 3, 10, tzinfo=timezone.utc),
        ]
        for i, t in enumerate(times):
            store.save(_make_snapshot(f"snap-{i}", generated_at=t))
        result = service.get_latest("TEST")
        assert result is not None
        assert result.snapshot_id == "snap-2"

    def test_get_previous_multiple(self, store, service):
        """get_previous returns the second-newest snapshot."""
        times = [
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 6, 15, tzinfo=timezone.utc),
            datetime(2025, 3, 10, tzinfo=timezone.utc),
        ]
        for i, t in enumerate(times):
            store.save(_make_snapshot(f"snap-{i}", generated_at=t))
        result = service.get_previous("TEST")
        assert result is not None
        assert result.snapshot_id == "snap-1"

    def test_compare_latest_multiple(self, store, service):
        """compare_latest compares the two most recent snapshots."""
        times = [
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 6, 15, tzinfo=timezone.utc),
            datetime(2025, 3, 10, tzinfo=timezone.utc),
        ]
        for i, t in enumerate(times):
            store.save(_make_snapshot(f"snap-{i}", generated_at=t))
        delta = service.compare_latest("TEST")
        assert isinstance(delta, ResearchDelta)
        assert delta.previous_snapshot_id == "snap-1"
        assert delta.current_snapshot_id == "snap-2"
class TestTickerFiltering:
    """Ticker filtering and case-insensitive matching."""

    def test_ticker_filtering(self, store, service):
        """Only snapshots for the requested ticker are returned."""
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.save(_make_snapshot("hdfc-1", ticker="HDFCBANK", generated_at=t1))
        store.save(_make_snapshot("icici-1", ticker="ICICIBANK", generated_at=t2))
        result = service.list_for_ticker("HDFCBANK")
        assert len(result) == 1
        assert result[0].snapshot_id == "hdfc-1"

    def test_case_insensitive_upper(self, store, service):
        """Uppercase ticker matches lowercase stored data."""
        store.save(_make_snapshot("snap-1", ticker="hdfcbank"))
        result = service.list_for_ticker("HDFCBANK")
        assert len(result) == 1

    def test_case_insensitive_lower(self, store, service):
        """Lowercase ticker matches uppercase stored data."""
        store.save(_make_snapshot("snap-1", ticker="HDFCBANK"))
        result = service.list_for_ticker("hdfcbank")
        assert len(result) == 1

    def test_case_insensitive_mixed(self, store, service):
        """Mixed case ticker matches stored data."""
        store.save(_make_snapshot("snap-1", ticker="HDFCBANK"))
        result = service.list_for_ticker("HdfcBank")
        assert len(result) == 1

    def test_unrelated_tickers_excluded(self, store, service):
        """Snapshots for other tickers are not returned."""
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.save(_make_snapshot("hdfc-1", ticker="HDFCBANK", generated_at=t1))
        store.save(_make_snapshot("icici-1", ticker="ICICIBANK", generated_at=t2))
        result = service.list_for_ticker("ICICIBANK")
        assert len(result) == 1
        assert result[0].snapshot_id == "icici-1"
        assert all(s.ticker.upper() == "ICICIBANK" for s in result)


class TestNonMutation:
    """Stored snapshots are not mutated."""

    def test_list_does_not_mutate(self, store, service):
        """list_for_ticker does not modify stored snapshots."""
        snap = _make_snapshot("snap-1", ticker="HDFCBANK")
        store.save(snap)
        original_id = snap.snapshot_id
        original_ticker = snap.ticker
        _ = service.list_for_ticker("HDFCBANK")
        loaded = store.load("snap-1")
        assert loaded.snapshot_id == original_id
        assert loaded.ticker == original_ticker

    def test_compare_latest_does_not_mutate(self, store, service):
        """compare_latest does not modify stored snapshots."""
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        old = _make_snapshot("snap-old", generated_at=t1)
        new = _make_snapshot("snap-new", generated_at=t2)
        store.save(old)
        store.save(new)
        _ = service.compare_latest("TEST")
        loaded_old = store.load("snap-old")
        loaded_new = store.load("snap-new")
        assert loaded_old.snapshot_id == "snap-old"
        assert loaded_new.snapshot_id == "snap-new"


class TestDeterministicBehavior:
    """Deterministic ordering and results."""

    def test_identical_timestamps_deterministic(self, store, service):
        """Snapshots with identical timestamps are ordered by snapshot_id."""
        t = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.save(_make_snapshot("snap-b", generated_at=t))
        store.save(_make_snapshot("snap-a", generated_at=t))
        result = service.list_for_ticker("TEST")
        assert len(result) == 2
        # Tie-breaker: snapshot_id ascending
        assert result[0].snapshot_id == "snap-a"
        assert result[1].snapshot_id == "snap-b"

    def test_repeatable_results(self, store, service):
        """Multiple calls with same data produce same results."""
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.save(_make_snapshot("snap-old", generated_at=t1))
        store.save(_make_snapshot("snap-new", generated_at=t2))
        result1 = service.list_for_ticker("TEST")
        result2 = service.list_for_ticker("TEST")
        ids1 = [s.snapshot_id for s in result1]
        ids2 = [s.snapshot_id for s in result2]
        assert ids1 == ids2