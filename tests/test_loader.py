"""Tests for the data loader."""

from pathlib import Path

import pytest

from investiq.data.loader import load_financial_data


# Path to the prepared data directory
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


class TestLoadFinancialData:
    """Test loading prepared JSON data into Pydantic models."""

    def test_load_hdfcbank(self):
        """Load HDFCBANK.json and validate the model."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)

        assert data.company.ticker == "HDFCBANK"
        assert data.company.name == "HDFC Bank Limited"
        assert data.company.company_type.value == "BANK"
        assert data.company.sector.value == "financial_services"

    def test_hdfcbank_provenance_is_synthetic(self):
        """HDFCBANK dataset must be explicitly marked SYNTHETIC."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        assert data.provenance is not None
        assert data.provenance.type.value == "SYNTHETIC"
        assert data.provenance.is_real_company_data is False
        assert data.provenance.generated_by == "AI"
        assert data.provenance.intended_use == "MVP testing only"

    def test_load_hdfcbank_case_insensitive(self):
        """Ticker lookup should be case-insensitive."""
        data = load_financial_data("hdfcbank", data_dir=DATA_DIR)
        assert data.company.ticker == "HDFCBANK"

    def test_load_five_years_income_statements(self):
        """Should have 5 years of income statements (FY2021–FY2025)."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        assert len(data.income_statements) == 5

        fiscal_years = [is_.fiscal_year for is_ in data.income_statements]
        assert "FY2021" in fiscal_years
        assert "FY2025" in fiscal_years

    def test_load_five_years_balance_sheets(self):
        """Should have 5 years of balance sheets (FY2021–FY2025)."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        assert len(data.balance_sheets) == 5

    def test_market_data_present(self):
        """Market data snapshot should be populated."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        assert data.market_data.current_price > 0
        assert data.market_data.shares_outstanding > 0

    def test_income_statement_required_fields(self):
        """Validate required income statement fields exist and are positive."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        for is_ in data.income_statements:
            assert is_.interest_income > 0
            assert is_.interest_expense > 0
            assert is_.net_interest_income > 0
            assert is_.total_operating_income > 0

    def test_synthetic_nii_discrepancy_diagnostic(self):
        """Explicitly report NII component discrepancies in synthetic test dataset.

        FY2021 matches: 122189 - 56270 = 65919
        FY2022-FY2025 contain synthetic discrepancies where reported NII
        differs from (interest_income - interest_expense).
        """
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        discrepancies = {}
        for is_ in data.income_statements:
            expected_nii = is_.interest_income - is_.interest_expense
            diff = abs(is_.net_interest_income - expected_nii)
            if diff >= 1.0:
                discrepancies[is_.fiscal_year] = {
                    "reported_nii": is_.net_interest_income,
                    "derived_nii": expected_nii,
                    "discrepancy": diff,
                }

        # Verify that synthetic data discrepancies are detected for FY2022-FY2025
        assert "FY2022" in discrepancies
        assert "FY2023" in discrepancies
        assert "FY2024" in discrepancies
        assert "FY2025" in discrepancies
        assert "FY2021" not in discrepancies

    def test_balance_sheet_advances_relationship(self):
        """Net advances should be <= gross advances."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        for bs in data.balance_sheets:
            assert bs.total_advances_net <= bs.total_advances_gross, (
                f"{bs.fiscal_year}: Net advances > gross advances"
            )

    def test_unknown_ticker_raises_error(self):
        """Loading an unknown ticker should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No prepared data found"):
            load_financial_data("UNKNOWN_TICKER", data_dir=DATA_DIR)

    def test_net_profit_positive(self):
        """HDFC Bank should have positive net profit for all years."""
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        for is_ in data.income_statements:
            assert is_.net_profit > 0, (
                f"{is_.fiscal_year}: Net profit should be positive"
            )
