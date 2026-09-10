"""Live integration test for BigQuery persistence layer.

Requires:
    - GOOGLE_APPLICATION_CREDENTIALS or valid ADC
    - GCP_PROJECT_ID  (or ADC default project)
    - BIGQUERY_DATASET (default: investiq)

Skip this test unless INVESTIQ_RUN_LIVE_BIGQUERY_TESTS=true.
"""

from __future__ import annotations

import os
import uuid
import logging
from datetime import date as dt_date, datetime, timezone

import pytest

from investiq.models.company import CompanyProfile, CompanyType, Sector
from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag
from investiq.models.financials import FinancialData, MarketData
from investiq.models.metrics import BankMetrics
from investiq.models.research import FindingCategory, ResearchFinding, ResearchSnapshot
from investiq.models.synthesis import CIOSynthesis
from investiq.models.valuation import ValuationMethod, ValuationResult, ValuationSummary
from investiq.storage.bigquery import BigQueryResearchRepository


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skip condition
# ---------------------------------------------------------------------------

def _skip_if_not_live() -> bool:
    """Return True if live BigQuery tests should be skipped."""
    return os.environ.get("INVESTIQ_RUN_LIVE_BIGQUERY_TESTS", "").lower() != "true"


skip_if_not_live = pytest.mark.skipif(
    _skip_if_not_live(),
    reason="Set INVESTIQ_RUN_LIVE_BIGQUERY_TESTS=true to run live BigQuery tests",
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_snapshot(ticker: str, company_name: str, snapshot_id: str) -> ResearchSnapshot:
    """Create a minimal ResearchSnapshot for testing."""
    company = CompanyProfile(
        ticker=ticker, name=company_name,
        sector=Sector.FINANCIAL_SERVICES, company_type=CompanyType.BANK,
    )
    return ResearchSnapshot(
        snapshot_id=snapshot_id,
        ticker=ticker,
        company=company,
        generated_at=datetime.now(timezone.utc),
        financial_data=FinancialData(
            company=company,
            income_statements=[],
            balance_sheets=[],
            market_data=MarketData(
                current_price=100.0, market_cap=1000.0,
                shares_outstanding=10.0, as_of=dt_date(2025, 1, 1),
            ),
        ),
        metrics=[
            BankMetrics(
                fiscal_year="FY2025",
                roe=15.0, roa=1.5, nim=3.5, casa_ratio=35.0,
                gross_npa_ratio=1.2, net_npa_ratio=0.4,
                cost_to_income=45.0, credit_cost=0.5,
                eps=80.0, book_value_per_share=500.0, evidence=[],
            ),
        ],
        valuation=ValuationSummary(
            methods=[
                ValuationResult(
                    method=ValuationMethod.PB_ROE,
                    estimated_fair_value=1800.0, current_price=1600.0,
                    upside_pct=12.5, assumptions=[], evidence=[],
                ),
            ],
            blended_fair_value=1800.0, verdict="Undervalued",
        ),
        findings=[
            ResearchFinding(
                analyst="financial_analyst",
                title="Strong Deposit Franchise",
                statement="Industry-leading CASA ratio supports NIM.",
                confidence=0.90,
                evidence_ids=[f"SYN-{ticker}-CASA-001"],
                category=FindingCategory.LIABILITY_FRANCHISE,
            ),
        ],
        evidence_chain=[
            EvidenceItem(
                evidence_id=f"SYN-{ticker}-CASA-001",
                tag=EvidenceTag.CALCULATION,
                label="CASA Ratio FY2025",
                source="Synthetic Fixture", value=35.0,
                domain=EvidenceDomain.FINANCIAL,
            ),
        ],
        cio_synthesis=CIOSynthesis(
            executive_summary="Strong bank with durable moat.",
            investment_thesis="Well-positioned for sustained growth.",
            overall_assessment="Conviction Buy",
            key_strengths=["Strong deposit franchise", "Conservative underwriting"],
            key_concerns=["Competition from fintech"],
            growth_drivers=["Digital adoption", "Rural expansion"],
            risks=["Macro slowdown", "Regulatory changes"],
            thesis_breakers=["Major credit event"],
            bull_case="Strong growth trajectory continues.",
            base_case="Stable performance with gradual improvement.",
            bear_case="Headwinds from macro environment.",
        ),
    )


def _get_test_id(ticker: str) -> str:
    """Generate a clearly identifiable test snapshot ID."""
    return f"live-test-{ticker.lower()}-{uuid.uuid4().hex[:8]}"
# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBigQueryLiveRepository:
    """Live integration tests against real BigQuery."""

    @classmethod
    def _make_repo(cls) -> BigQueryResearchRepository:
        return BigQueryResearchRepository(
            project_id=os.environ.get("GCP_PROJECT_ID"),
            dataset_id=os.environ.get("BIGQUERY_DATASET", "investiq"),
            location=os.environ.get("BIGQUERY_LOCATION", "asia-south1"),
        )

    @skip_if_not_live
    def test_01_initialize_dataset(self):
        """Verify dataset and tables can be created/verified."""
        repo = self._make_repo()
        repo.initialize_dataset()

        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound

        client = repo.client
        ds_ref = bigquery.DatasetReference(client.project, repo.dataset_id)
        ds = client.get_dataset(ds_ref)
        assert ds.location == repo.location

        for table_name in [
            repo.TABLE_SNAPSHOTS,
            repo.TABLE_METRICS,
            repo.TABLE_FINDINGS,
            repo.TABLE_EVIDENCE,
            repo.TABLE_SCENARIOS,
            repo.TABLE_THESIS_ITEMS,
        ]:
            table_ref = f"{client.project}.{repo.dataset_id}.{table_name}"
            try:
                client.get_table(table_ref)
            except NotFound:
                pytest.fail(f"Table {table_ref} was not created")

    @skip_if_not_live
    def test_02_persist_and_query_hdfc(self):
        """Persist HDFC snapshot and verify all 6 tables have rows."""
        hdfc_id = _get_test_id("HDFCBANK")
        snapshot = _make_snapshot("HDFCBANK", "HDFC Bank Limited", hdfc_id)
        repo = self._make_repo()
        repo.save_snapshot(snapshot)

        client = repo.client
        dataset = repo.dataset_id

        snap_rows = list(client.query(
            f"SELECT snapshot_id, ticker FROM "
            f"`{client.project}.{dataset}.research_snapshots` "
            f"WHERE snapshot_id = '{hdfc_id}'"
        ).result())
        assert len(snap_rows) == 1
        assert snap_rows[0]["snapshot_id"] == hdfc_id
        assert snap_rows[0]["ticker"] == "HDFCBANK"

        for table, expected_min in [
            ("research_metrics", 1),
            ("research_findings", 1),
            ("research_evidence", 1),
            ("research_scenarios", 3),
            ("research_thesis_items", 1),
        ]:
            rows = list(client.query(
                f"SELECT snapshot_id FROM "
                f"`{client.project}.{dataset}.{table}` "
                f"WHERE snapshot_id = '{hdfc_id}'"
            ).result())
            assert len(rows) >= expected_min, (
                f"Expected >= {expected_min} rows in {table}, got {len(rows)}"
            )
    @skip_if_not_live
    def test_03_persist_and_query_icici(self):
        """Persist ICICI snapshot and verify."""
        icici_id = _get_test_id("ICICIBANK")
        snapshot = _make_snapshot("ICICIBANK", "ICICI Bank Limited", icici_id)
        repo = self._make_repo()
        repo.save_snapshot(snapshot)

        client = repo.client
        dataset = repo.dataset_id

        snap_rows = list(client.query(
            f"SELECT snapshot_id, ticker FROM "
            f"`{client.project}.{dataset}.research_snapshots` "
            f"WHERE snapshot_id = '{icici_id}'"
        ).result())
        assert len(snap_rows) == 1
        assert snap_rows[0]["ticker"] == "ICICIBANK"

    @skip_if_not_live
    def test_04_idempotency(self):
        """Saving same snapshot_id twice must not create duplicate rows.

        Idempotency strategy (in _merge_rows):
            1. DELETE all existing rows for snapshot_id
            2. INSERT current rows via load job (not streaming)

        After two saves of the same snapshot_id, each table must have the
        EXACT same row count as after the first save — no duplication.
        """
        snap_id = _get_test_id("IDEMPOTENCY")
        snapshot = _make_snapshot("IDEMPOTENCY", "Test Company", snap_id)
        repo = self._make_repo()
        client = repo.client
        dataset = repo.dataset_id
        all_tables = [
            "research_snapshots",
            "research_metrics",
            "research_findings",
            "research_evidence",
            "research_scenarios",
            "research_thesis_items",
        ]

        # Save once and record row counts per table
        repo.save_snapshot(snapshot)
        counts_1 = {}
        for table_name in all_tables:
            rows = list(client.query(
                f"SELECT COUNT(*) as cnt FROM "
                f"`{client.project}.{dataset}.{table_name}` "
                f"WHERE snapshot_id = '{snap_id}'"
            ).result())
            counts_1[table_name] = rows[0]["cnt"]

        # Save the exact same snapshot again
        repo.save_snapshot(snapshot)

        # Record row counts after the second save
        counts_2 = {}
        for table_name in all_tables:
            rows = list(client.query(
                f"SELECT COUNT(*) as cnt FROM "
                f"`{client.project}.{dataset}.{table_name}` "
                f"WHERE snapshot_id = '{snap_id}'"
            ).result())
            counts_2[table_name] = rows[0]["cnt"]

        # Idempotency: counts must be identical, not growing
        for table_name in all_tables:
            assert counts_1[table_name] == counts_2[table_name], (
                f"Table {table_name}: had {counts_1[table_name]} rows after first save, "
                f"but {counts_2[table_name]} rows after second save "
                f"(idempotency violated — rows duplicated)"
            )

    @skip_if_not_live
    def test_05_cross_company_isolation(self):
        """Verify HDFC data does not contaminate ICICI data."""
        hdfc_id = _get_test_id("HDFCBANK-ISO")
        icici_id = _get_test_id("ICICIBANK-ISO")

        hdfc = _make_snapshot("HDFCBANK", "HDFC Bank Limited", hdfc_id)
        icici = _make_snapshot("ICICIBANK", "ICICI Bank Limited", icici_id)

        repo = self._make_repo()
        repo.save_snapshot(hdfc)
        repo.save_snapshot(icici)

        client = repo.client
        dataset = repo.dataset_id

        icici_snap = list(client.query(
            f"SELECT ticker FROM "
            f"`{client.project}.{dataset}.research_snapshots` "
            f"WHERE snapshot_id = '{icici_id}'"
        ).result())
        assert icici_snap[0]["ticker"] == "ICICIBANK"

        hdfc_snap = list(client.query(
            f"SELECT ticker FROM "
            f"`{client.project}.{dataset}.research_snapshots` "
            f"WHERE snapshot_id = '{hdfc_id}'"
        ).result())
        assert hdfc_snap[0]["ticker"] == "HDFCBANK"

    @skip_if_not_live
    def test_99_cleanup_test_data(self):
        """Delete all rows with snapshot_id starting with 'live-test-'.

        Uses the same DML DELETE approach as _merge_rows. Rows written by the
        current load-job implementation (load_table_from_json) are in managed
        storage and are immediately available for DML deletion.

        Rows written by the PREVIOUS streaming implementation (insert_rows_json)
        may still be in the BigQuery streaming buffer. BigQuery does not allow
        DML (DELETE/UPDATE/MERGE) on buffered data for up to ~90 minutes after
        ingestion. Such rows are counted and reported transparently.
        """
        repo = self._make_repo()
        client = repo.client
        dataset = repo.dataset_id
        all_tables = [
            "research_snapshots",
            "research_metrics",
            "research_findings",
            "research_evidence",
            "research_scenarios",
            "research_thesis_items",
        ]

        remaining = {}
        for table_name in all_tables:
            try:
                client.query(
                    f"DELETE FROM `{client.project}.{dataset}.{table_name}` "
                    f"WHERE snapshot_id LIKE 'live-test-%'"
                ).result()
            except Exception as exc:
                logger.warning(
                    "DML cleanup on %s encountered: %s",
                    table_name, exc,
                )
                logger.warning(
                    "This typically means data from a previous run using "
                    "insert_rows_json is still in BigQuery's ~90-minute streaming "
                    "buffer. Rows written by the current load-job implementation "
                    "are in managed storage and are cleanable immediately."
                )

            # Count what remains after the cleanup attempt
            rows = list(client.query(
                f"SELECT COUNT(*) as cnt FROM "
                f"`{client.project}.{dataset}.{table_name}` "
                f"WHERE snapshot_id LIKE 'live-test-%'"
            ).result())
            cnt = rows[0]["cnt"]
            if cnt > 0:
                remaining[table_name] = cnt

        if remaining:
            pytest.fail(
                f"Stale BigQuery streaming-buffer rows remain: {remaining}. "
                f"These were created by a previous test implementation using the "
                f"streaming insert_rows_json API. BigQuery does not allow DML on "
                f"streaming-buffered data for up to ~90 minutes. "
                f"Rows written by the current load-job implementation have been "
                f"cleaned up successfully. The stale rows will auto-clear and "
                f"are harmless to production data."
            )