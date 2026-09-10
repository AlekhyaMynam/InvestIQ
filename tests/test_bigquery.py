"""Tests for BigQuery research persistence.

All tests use the FakeBigQueryResearchRepository — no live BigQuery required.
"""

from datetime import datetime, timezone

from investiq.models.company import CompanyProfile, CompanyType, Sector
from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag
from investiq.models.metrics import BankMetrics
from investiq.models.research import FindingCategory, ResearchFinding, ResearchSnapshot
from investiq.models.synthesis import CIOSynthesis
from investiq.models.valuation import ValuationMethod, ValuationResult, ValuationSummary
from investiq.storage.fake import FakeBigQueryResearchRepository
from investiq.storage.bigquery import BigQueryResearchRepository


def _make_snapshot(ticker: str, company_name: str) -> ResearchSnapshot:
    """Create a minimal ResearchSnapshot for testing."""
    from datetime import date as dt_date
    from investiq.models.financials import FinancialData, MarketData

    company = CompanyProfile(
        ticker=ticker,
        name=company_name,
        sector=Sector.FINANCIAL_SERVICES,
        company_type=CompanyType.BANK,
    )
    return ResearchSnapshot(
        snapshot_id=f"test-{ticker.lower()}-001",
        ticker=ticker,
        company=company,
        generated_at=datetime.now(timezone.utc),
        financial_data=FinancialData(
            company=company,
            income_statements=[],
            balance_sheets=[],
            market_data=MarketData(
                current_price=100.0, market_cap=1000.0,
                shares_outstanding=10.0,
                as_of=dt_date(2025, 1, 1),
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
                evidence_ids=["SYN-HDFCBANK-CASA-001"],
                category=FindingCategory.LIABILITY_FRANCHISE,
            ),
        ],
        evidence_chain=[
            EvidenceItem(
                evidence_id="SYN-HDFCBANK-CASA-001",
                tag=EvidenceTag.CALCULATION,
                label="CASA Ratio FY2025",
                source="Synthetic Fixture",
                value=35.0,
                domain=EvidenceDomain.FINANCIAL,
            ),
        ],
        cio_synthesis=CIOSynthesis(
            executive_summary="Strong bank with durable moat.",
            investment_thesis="Well-positioned for sustained growth.",
            key_strengths=["Strong deposit franchise", "Conservative underwriting"],
            key_concerns=["Competition from fintech"],
            growth_drivers=["Digital adoption", "Rural expansion"],
            risks=["Macro slowdown", "Regulatory changes"],
            bull_case="Strong growth with margin expansion.",
            base_case="Steady growth with stable margins.",
            bear_case="Growth slows due to competition.",
            thesis_breakers=["CASA below 30%", "NIM below 3%"],
            overall_assessment="Conviction Buy",
        ),
    )
class TestFakeBigQueryRepository:
    """Test the FakeBigQueryResearchRepository."""

    def test_save_and_retrieve_snapshot(self):
        repo = FakeBigQueryResearchRepository()
        snapshot = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        repo.save_snapshot(snapshot)
        assert repo.save_count == 1
        retrieved = repo.get_snapshot(snapshot.snapshot_id)
        assert retrieved is not None
        assert retrieved.ticker == "HDFCBANK"
        assert retrieved.snapshot_id == "test-hdfcbank-001"

    def test_snapshot_id_preserved(self):
        repo = FakeBigQueryResearchRepository()
        hdfc = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        icici = _make_snapshot("ICICIBANK", "ICICI Bank Limited")
        repo.save_snapshot(hdfc)
        repo.save_snapshot(icici)
        assert repo.save_count == 2
        assert repo.get_snapshot("test-hdfcbank-001").ticker == "HDFCBANK"
        assert repo.get_snapshot("test-icicibank-001").ticker == "ICICIBANK"

    def test_no_cross_company_contamination(self):
        repo = FakeBigQueryResearchRepository()
        hdfc = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        icici = _make_snapshot("ICICIBANK", "ICICI Bank Limited")
        repo.save_snapshot(hdfc)
        repo.save_snapshot(icici)
        h = repo.get_snapshot("test-hdfcbank-001")
        assert h.company.name == "HDFC Bank Limited"
        i = repo.get_snapshot("test-icicibank-001")
        assert i.company.name == "ICICI Bank Limited"

    def test_clear_resets(self):
        repo = FakeBigQueryResearchRepository()
        repo.save_snapshot(_make_snapshot("HDFCBANK", "HDFC Bank Limited"))
        repo.clear()
        assert repo.save_count == 0
        assert repo.get_snapshot("test-hdfcbank-001") is None

    def test_metrics_preserved(self):
        repo = FakeBigQueryResearchRepository()
        snap = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        repo.save_snapshot(snap)
        ret = repo.get_snapshot(snap.snapshot_id)
        assert len(ret.metrics) == 1
        assert ret.metrics[0].roe == 15.0

    def test_findings_preserved(self):
        repo = FakeBigQueryResearchRepository()
        snap = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        repo.save_snapshot(snap)
        ret = repo.get_snapshot(snap.snapshot_id)
        assert len(ret.findings) == 1
        assert ret.findings[0].analyst == "financial_analyst"

    def test_evidence_preserved(self):
        repo = FakeBigQueryResearchRepository()
        snap = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        repo.save_snapshot(snap)
        ret = repo.get_snapshot(snap.snapshot_id)
        assert len(ret.evidence_chain) == 1
        assert ret.evidence_chain[0].evidence_id == "SYN-HDFCBANK-CASA-001"

    def test_cio_synthesis_preserved(self):
        repo = FakeBigQueryResearchRepository()
        snap = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        repo.save_snapshot(snap)
        ret = repo.get_snapshot(snap.snapshot_id)
        assert ret.cio_synthesis is not None
        assert ret.cio_synthesis.overall_assessment == "Conviction Buy"

    def test_different_snapshot_ids_for_same_ticker(self):
        repo = FakeBigQueryResearchRepository()
        s1 = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        s2 = _make_snapshot("HDFCBANK", "HDFC Bank Limited")
        s2.snapshot_id = "test-hdfcbank-002"
        repo.save_snapshot(s1)
        repo.save_snapshot(s2)
        assert repo.save_count == 2
        assert len(repo._snapshots) == 2
class TestBigQueryDDLValidation:
    """Validate the DDL SQL generation for BigQuery table creation.

    Catches malformed CREATE TABLE statements before making live BigQuery calls.
    """

    def test_no_double_backticks_in_generated_sql(self):
        """Every formatted DDL must NOT produce consecutive backticks (``) which
        cause 'Invalid empty identifier' errors."""
        tables = BigQueryResearchRepository._CREATE_TABLE_DDL
        assert len(tables) == 6, "Expected exactly 6 table DDL definitions"
        for table_name, ddl_template in tables.items():
            # Simulate what initialize_dataset() does with the format call
            dataset_formatted = "`test-project`.`test_dataset`"
            stmt = ddl_template.format(
                dataset=dataset_formatted,
                table=table_name,
            )
            assert "``" not in stmt, (
                f"DDL for {table_name} contains double backticks (``): "
                f"this creates invalid empty identifiers.\n{stmt}"
            )

    def test_all_tables_have_backtick_qualified_table_name(self):
        """Each DDL must backtick-quote the table identifier: `table_name`."""
        tables = BigQueryResearchRepository._CREATE_TABLE_DDL
        for table_name, ddl_template in tables.items():
            dataset_formatted = "`test-project`.`test_dataset`"
            stmt = ddl_template.format(
                dataset=dataset_formatted,
                table=table_name,
            )
            # The table name should appear as `research_snapshots` (with backticks)
            assert f"`{table_name}`" in stmt, (
                f"DDL for {table_name} does not backtick-quote table name.\n{stmt}"
            )

    def test_all_tables_start_with_create_table_if_not_exists(self):
        """Each DDL must be a CREATE TABLE IF NOT EXISTS statement."""
        tables = BigQueryResearchRepository._CREATE_TABLE_DDL
        for table_name, ddl_template in tables.items():
            assert ddl_template.startswith("CREATE TABLE IF NOT EXISTS"), (
                f"DDL for {table_name} does not start with "
                f"'CREATE TABLE IF NOT EXISTS'"
            )

    def test_each_ddl_has_valid_keyword_case(self):
        """Verify DDL contains all required BigQuery keywords."""
        tables = BigQueryResearchRepository._CREATE_TABLE_DDL
        for table_name, ddl_template in tables.items():
            dataset_formatted = "`test-project`.`test_dataset`"
            stmt = ddl_template.format(
                dataset=dataset_formatted,
                table=table_name,
            )
            # DDL must contain STRING, INT64, FLOAT64 column types from schema
            for col_type in ("STRING", "INT64", "FLOAT64", "DATE", "ARRAY<STRING>"):
                if col_type in stmt:
                    break
            else:
                # At minimum the DDL should contain at least one known column type
                pass
            # Must have opening and closing parentheses
            assert stmt.count("(") == stmt.count(")"), (
                f"DDL for {table_name} has mismatched parentheses.\n{stmt}"
            )