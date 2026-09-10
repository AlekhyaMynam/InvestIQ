"""Tests for ResearchSnapshotStore — local JSON persistence.

All tests use tmp_path and make zero external API calls.
"""

from pathlib import Path

import pytest

from investiq.llm.mock import MockLLMProvider
from investiq.models.research import ResearchSnapshot
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
from investiq.research.orchestrator import ResearchOrchestrator
from investiq.research.snapshot_store import ResearchSnapshotStore


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


@pytest.fixture
def store(tmp_path) -> ResearchSnapshotStore:
    """Create a ResearchSnapshotStore in a temporary directory."""
    return ResearchSnapshotStore(store_dir=tmp_path)


@pytest.fixture(scope="module")
def snapshot() -> ResearchSnapshot:
    """Create a realistic ResearchSnapshot using the HDFCBANK fixture and
    MockLLMProvider, which makes zero external API calls."""
    provider = MockLLMProvider(simulated_latency_ms=0.0)
    orchestrator = ResearchOrchestrator(provider=provider, data_dir=DATA_DIR)
    evidence = get_synthetic_hdfcbank_evidence()
    return orchestrator.research("HDFCBANK", evidence_items=evidence)


def _make_minimal_snapshot(snapshot_id: str) -> ResearchSnapshot:
    """Create a minimal ResearchSnapshot for testing storage mechanics."""
    from datetime import date, datetime, timezone
    from investiq.models.company import CompanyProfile, Sector, CompanyType
    from investiq.models.financials import FinancialData, MarketData
    from investiq.models.valuation import ValuationSummary

    return ResearchSnapshot(
        snapshot_id=snapshot_id,
        ticker="TEST",
        company=CompanyProfile(
            ticker="TEST", name="Test",
            sector=Sector.FINANCIAL_SERVICES,
            company_type=CompanyType.BANK,
        ),
        generated_at=datetime.now(timezone.utc),
        financial_data=FinancialData(
            company=CompanyProfile(
                ticker="TEST", name="Test",
                sector=Sector.FINANCIAL_SERVICES,
                company_type=CompanyType.BANK,
            ),
            income_statements=[],
            balance_sheets=[],
            market_data=MarketData(
                current_price=100.0, market_cap=1000.0,
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


class TestSnapshotStoreSave:
    """Tests for the save() method."""

    def test_save_creates_json_file(self, store, snapshot):
        """save() creates a JSON file on disk."""
        result_path = store.save(snapshot)
        assert result_path.exists()
        assert result_path.suffix == ".json"
        assert result_path.is_file()
        assert snapshot.snapshot_id in result_path.name

    def test_save_returns_path(self, store, snapshot):
        """save() returns a Path object."""
        result_path = store.save(snapshot)
        assert isinstance(result_path, Path)
        assert result_path.is_absolute()

    def test_save_contents_are_valid_json(self, store, snapshot):
        """The saved file contains valid JSON."""
        path = store.save(snapshot)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert data["snapshot_id"] == snapshot.snapshot_id
        assert data["ticker"] == snapshot.ticker

    def test_save_twice_no_duplicates(self, store, snapshot):
        """Saving the same snapshot twice does not create duplicate files."""
        path1 = store.save(snapshot)
        path2 = store.save(snapshot)
        assert path1 == path2
        assert path1.exists()
        json_files = list(store.store_dir.glob("*.json"))
        assert len(json_files) == 1


class TestSnapshotStoreLoad:
    """Tests for the load() method."""

    def test_saved_snapshot_can_be_loaded(self, store, snapshot):
        """A saved snapshot can be loaded back as a ResearchSnapshot."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert isinstance(loaded, ResearchSnapshot)

    def test_snapshot_id_preserved(self, store, snapshot):
        """snapshot_id survives save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert loaded.snapshot_id == snapshot.snapshot_id

    def test_ticker_preserved(self, store, snapshot):
        """ticker survives save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert loaded.ticker == snapshot.ticker

    def test_company_preserved(self, store, snapshot):
        """Company profile survives save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert loaded.company.ticker == snapshot.company.ticker
        assert loaded.company.name == snapshot.company.name
        assert loaded.company.sector == snapshot.company.sector
        assert loaded.company.company_type == snapshot.company.company_type

    def test_generated_at_preserved(self, store, snapshot):
        """generated_at datetime survives save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert loaded.generated_at == snapshot.generated_at

    def test_metrics_preserved(self, store, snapshot):
        """BankMetrics survive save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert len(loaded.metrics) == len(snapshot.metrics)
        for lm, sm in zip(loaded.metrics, snapshot.metrics):
            assert lm.fiscal_year == sm.fiscal_year
            assert lm.roe == sm.roe
            assert lm.eps == sm.eps

    def test_valuation_preserved(self, store, snapshot):
        """ValuationSummary survives save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert loaded.valuation.blended_fair_value == snapshot.valuation.blended_fair_value
        assert loaded.valuation.verdict == snapshot.valuation.verdict
        assert len(loaded.valuation.methods) == len(snapshot.valuation.methods)

    def test_findings_preserved(self, store, snapshot):
        """ResearchFindings survive save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert len(loaded.findings) == len(snapshot.findings)
        for lf, sf in zip(loaded.findings, snapshot.findings):
            assert lf.analyst == sf.analyst
            assert lf.title == sf.title
            assert lf.statement == sf.statement
            assert lf.confidence == sf.confidence
            assert lf.evidence_ids == sf.evidence_ids
            assert lf.category == sf.category

    def test_evidence_chain_preserved(self, store, snapshot):
        """Evidence items survive save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert len(loaded.evidence_chain) == len(snapshot.evidence_chain)
        for le, se in zip(loaded.evidence_chain, snapshot.evidence_chain):
            assert le.evidence_id == se.evidence_id
            assert le.tag == se.tag
            assert le.label == se.label
            assert le.source == se.source
            assert le.value == se.value

    def test_metadata_preserved(self, store, snapshot):
        """Metadata dict survives save/load round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        assert loaded.metadata == snapshot.metadata

    def test_enums_preserved(self, store, snapshot):
        """Enum values in nested models survive round trip."""
        store.save(snapshot)
        loaded = store.load(snapshot.snapshot_id)
        from investiq.models.research import FindingCategory
        for finding in loaded.findings:
            assert isinstance(finding.category, FindingCategory)
        from investiq.models.evidence import EvidenceTag
        for ev in loaded.evidence_chain:
            assert isinstance(ev.tag, EvidenceTag)

    def test_load_missing_snapshot(self, store):
        """load() raises FileNotFoundError for a nonexistent snapshot."""
        with pytest.raises(FileNotFoundError):
            store.load("nonexistent-snapshot-id")

    def test_load_invalid_id_raises_value_error(self, store):
        """load() raises ValueError for an invalid snapshot_id."""
        with pytest.raises(ValueError):
            store.load("../path/traversal")


class TestSnapshotStoreExists:
    """Tests for the exists() method."""

    def test_exists_returns_true_for_saved(self, store, snapshot):
        """exists() returns True after saving a snapshot."""
        store.save(snapshot)
        assert store.exists(snapshot.snapshot_id) is True

    def test_exists_returns_false_for_missing(self, store):
        """exists() returns False for a nonexistent snapshot."""
        assert store.exists("nonexistent-id") is False

    def test_exists_after_delete(self, store, snapshot):
        """exists() returns False after deleting a snapshot."""
        store.save(snapshot)
        store.delete(snapshot.snapshot_id)
        assert store.exists(snapshot.snapshot_id) is False


class TestSnapshotStoreList:
    """Tests for the list_snapshots() method."""

    def test_list_empty(self, store):
        """list_snapshots() returns [] for an empty store."""
        assert store.list_snapshots() == []

    def test_list_single(self, store, snapshot):
        """list_snapshots() returns saved snapshot IDs."""
        store.save(snapshot)
        ids = store.list_snapshots()
        assert snapshot.snapshot_id in ids

    def test_list_deterministic_ordering(self, store):
        """list_snapshots() returns IDs in deterministic (sorted) order."""
        sids = ["z-snapshot", "a-snapshot", "m-snapshot"]
        for sid in sids:
            dummy = _make_minimal_snapshot(sid)
            store.save(dummy)
        ids = store.list_snapshots()
        assert ids == sorted(ids)
        assert ids == ["a-snapshot", "m-snapshot", "z-snapshot"]

    def test_list_multiple_snapshots_coexist(self, store, snapshot):
        """Multiple saved snapshots appear in list_snapshots."""
        sid1 = snapshot.snapshot_id
        store.save(snapshot)
        snap2 = _make_minimal_snapshot("second-snapshot")
        store.save(snap2)
        ids = store.list_snapshots()
        assert sid1 in ids
        assert "second-snapshot" in ids
        assert len(ids) == 2


class TestSnapshotStoreDelete:
    """Tests for the delete() method."""

    def test_delete_removes_file(self, store, snapshot):
        """delete() removes the snapshot file from disk."""
        store.save(snapshot)
        path = store.store_dir / f"{snapshot.snapshot_id}.json"
        assert path.exists()
        store.delete(snapshot.snapshot_id)
        assert not path.exists()

    def test_delete_missing_raises(self, store):
        """delete() raises FileNotFoundError for missing snapshot."""
        with pytest.raises(FileNotFoundError):
            store.delete("nonexistent-id")

    def test_delete_after_delete_raises(self, store, snapshot):
        """Deleting a snapshot twice raises FileNotFoundError."""
        store.save(snapshot)
        store.delete(snapshot.snapshot_id)
        with pytest.raises(FileNotFoundError):
            store.delete(snapshot.snapshot_id)


class TestSnapshotStoreInvalidInputs:
    """Tests for path traversal protection and invalid inputs."""

    def test_save_invalid_snapshot_id_raises(self, store):
        """save() raises ValueError if snapshot_id contains path traversal."""
        bad_snapshot = _make_minimal_snapshot("../etc/passwd")
        with pytest.raises(ValueError):
            store.save(bad_snapshot)

    def test_load_path_traversal_raises(self, store):
        """load() raises ValueError on path traversal attempt."""
        with pytest.raises(ValueError):
            store.load("../../secret")

    def test_exists_invalid_id_raises(self, store):
        """exists() raises ValueError on invalid snapshot_id."""
        with pytest.raises(ValueError):
            store.exists("../../../windows/system32")

    def test_delete_path_traversal_raises(self, store):
        """delete() raises ValueError on path traversal attempt."""
        with pytest.raises(ValueError):
            store.delete("..\\..\\config.json")

    def test_empty_snapshot_id_raises(self, store):
        """Empty snapshot_id raises ValueError."""
        with pytest.raises(ValueError):
            store.load("")


class TestSnapshotStoreDirectoryCreation:
    """Tests for store directory creation."""

    def test_store_creates_directory(self, tmp_path):
        """Store creates the directory if it does not exist."""
        new_dir = tmp_path / "nested" / "snapshot" / "store"
        assert not new_dir.exists()
        store = ResearchSnapshotStore(store_dir=new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_store_uses_existing_directory(self, tmp_path):
        """Store uses an existing directory without error."""
        existing = tmp_path / "existing"
        existing.mkdir()
        store = ResearchSnapshotStore(store_dir=existing)
        assert store.store_dir == existing.resolve()