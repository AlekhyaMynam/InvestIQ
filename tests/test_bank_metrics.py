"""Tests for bank-specific financial metric calculations.

Tests cover:
- Individual metric calculations with known inputs
- Full pipeline from FinancialData → BankMetrics
- Evidence traceability
- Edge cases (zero denominators, missing prior year)
"""

from pathlib import Path

import pytest

from investiq.calculators.bank_metrics import (
    calculate_bvps,
    calculate_casa_ratio,
    calculate_cost_to_income,
    calculate_credit_cost,
    calculate_eps,
    calculate_gross_npa_ratio,
    calculate_net_npa_ratio,
    calculate_nim,
    calculate_roa,
    calculate_roe,
    compute_bank_metrics,
)
from investiq.data.loader import load_financial_data
from investiq.models.evidence import EvidenceTag


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


class TestIndividualMetrics:
    """Test each metric calculation function in isolation."""

    def test_roe_with_average_equity(self):
        """ROE = Net Profit / Avg Equity."""
        # Net profit = 100, equity current = 600, equity previous = 400
        # Avg equity = 500, ROE = 100/500 * 100 = 20%
        assert calculate_roe(100, 600, 400) == pytest.approx(20.0)

    def test_roe_without_prior_year(self):
        """First year: ROE uses current equity only."""
        # Net profit = 100, equity = 500, no prior year
        # ROE = 100/500 * 100 = 20%
        assert calculate_roe(100, 500, None) == pytest.approx(20.0)

    def test_roe_zero_equity(self):
        """Zero equity should return 0 (guard clause)."""
        assert calculate_roe(100, 0, 0) == 0.0

    def test_roa(self):
        """ROA = Net Profit / Avg Total Assets."""
        # Net profit = 50, assets current = 3000, assets previous = 2000
        # Avg = 2500, ROA = 50/2500 * 100 = 2%
        assert calculate_roa(50, 3000, 2000) == pytest.approx(2.0)

    def test_nim(self):
        """NIM = NII / Avg Total Assets."""
        # NII = 100, assets current = 3000, assets previous = 2000
        # Avg = 2500, NIM = 100/2500 * 100 = 4%
        assert calculate_nim(100, 3000, 2000) == pytest.approx(4.0)

    def test_casa_ratio(self):
        """CASA Ratio = CASA / Total Deposits."""
        # CASA = 450, Total = 1000, ratio = 45%
        assert calculate_casa_ratio(450, 1000) == pytest.approx(45.0)

    def test_gross_npa_ratio(self):
        """Gross NPA Ratio = Gross NPA / Gross Advances."""
        # Gross NPA = 15, Gross Advances = 1000, ratio = 1.5%
        assert calculate_gross_npa_ratio(15, 1000) == pytest.approx(1.5)

    def test_net_npa_ratio(self):
        """Net NPA Ratio = Net NPA / Net Advances."""
        assert calculate_net_npa_ratio(5, 1000) == pytest.approx(0.5)

    def test_cost_to_income(self):
        """Cost-to-Income = Opex / Total Operating Income."""
        assert calculate_cost_to_income(40, 100) == pytest.approx(40.0)

    def test_credit_cost(self):
        """Credit Cost = Provisions / Avg Gross Advances."""
        # Provisions = 10, adv current = 1200, adv previous = 800
        # Avg = 1000, credit cost = 10/1000 * 100 = 1%
        assert calculate_credit_cost(10, 1200, 800) == pytest.approx(1.0)

    def test_eps(self):
        """EPS = Net Profit (Cr) / Shares Outstanding (Cr) = ₹ per share."""
        # Net profit = 31867 Cr, shares = 553 Cr
        eps = calculate_eps(31867, 553)
        assert eps == pytest.approx(57.63, abs=0.01)

    def test_bvps(self):
        """BVPS = Total Equity (Cr) / Shares Outstanding (Cr) = ₹ per share."""
        bvps = calculate_bvps(182377, 553)
        assert bvps == pytest.approx(329.79, abs=0.01)


class TestComputeBankMetricsPipeline:
    """Test the full compute_bank_metrics pipeline with real HDFC Bank data."""

    @pytest.fixture
    def financial_data(self):
        return load_financial_data("HDFCBANK", data_dir=DATA_DIR)

    def test_returns_five_years(self, financial_data):
        """Should compute metrics for all 5 fiscal years."""
        metrics = compute_bank_metrics(financial_data)
        assert len(metrics) == 5

    def test_ordered_by_fiscal_year(self, financial_data):
        """Results should be ordered oldest → newest."""
        metrics = compute_bank_metrics(financial_data)
        years = [m.fiscal_year for m in metrics]
        assert years == sorted(years)

    def test_roe_in_reasonable_range(self, financial_data):
        """HDFC Bank ROE should be in 10–25% range."""
        metrics = compute_bank_metrics(financial_data)
        for m in metrics:
            assert 10 <= m.roe <= 25, (
                f"{m.fiscal_year}: ROE {m.roe}% outside expected range"
            )

    def test_roa_in_reasonable_range(self, financial_data):
        """HDFC Bank ROA should be in 1.0–2.5% range."""
        metrics = compute_bank_metrics(financial_data)
        for m in metrics:
            assert 1.0 <= m.roa <= 2.5, (
                f"{m.fiscal_year}: ROA {m.roa}% outside expected range"
            )

    def test_nim_in_reasonable_range(self, financial_data):
        """HDFC Bank NIM should be in 2.5–5.0% range."""
        metrics = compute_bank_metrics(financial_data)
        for m in metrics:
            assert 2.5 <= m.nim <= 5.0, (
                f"{m.fiscal_year}: NIM {m.nim}% outside expected range"
            )

    def test_gross_npa_below_threshold(self, financial_data):
        """HDFC Bank Gross NPA should be below 3%."""
        metrics = compute_bank_metrics(financial_data)
        for m in metrics:
            assert m.gross_npa_ratio < 3.0, (
                f"{m.fiscal_year}: Gross NPA {m.gross_npa_ratio}% too high"
            )

    def test_eps_positive(self, financial_data):
        """EPS should be positive for all years."""
        metrics = compute_bank_metrics(financial_data)
        for m in metrics:
            assert m.eps > 0, f"{m.fiscal_year}: EPS should be positive"

    def test_evidence_attached(self, financial_data):
        """Every BankMetrics should have evidence items."""
        metrics = compute_bank_metrics(financial_data)
        for m in metrics:
            assert len(m.evidence) == 10, (
                f"{m.fiscal_year}: Expected 10 evidence items, got {len(m.evidence)}"
            )

    def test_evidence_tags_are_calculation(self, financial_data):
        """All evidence items from bank metrics should be CALCULATION type."""
        metrics = compute_bank_metrics(financial_data)
        for m in metrics:
            for ev in m.evidence:
                assert ev.tag == EvidenceTag.CALCULATION

    def test_evidence_has_uuid(self, financial_data):
        """Every evidence item should have a unique evidence_id."""
        metrics = compute_bank_metrics(financial_data)
        all_ids = []
        for m in metrics:
            for ev in m.evidence:
                assert ev.evidence_id is not None
                assert len(ev.evidence_id) > 0
                all_ids.append(ev.evidence_id)
        # All IDs should be unique
        assert len(all_ids) == len(set(all_ids))

    def test_latest_year_metrics(self, financial_data):
        """Spot-check FY2025 metrics for HDFC Bank."""
        metrics = compute_bank_metrics(financial_data)
        fy25 = [m for m in metrics if m.fiscal_year == "FY2025"][0]

        # These are approximate expected values based on the prepared data
        assert fy25.eps > 0
        assert fy25.book_value_per_share > 0
        assert fy25.casa_ratio > 30   # HDFC Bank has strong CASA
        assert fy25.cost_to_income > 30 and fy25.cost_to_income < 50
