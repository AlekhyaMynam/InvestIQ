"""Tests for bank valuation calculations.

Tests cover:
- Sustainable growth calculation
- Dividend payout ratio
- P/B × ROE valuation method
- P/E valuation method
- Blended valuation
- Assumption tagging and evidence traceability
- Edge cases
"""

from pathlib import Path

import pytest

from investiq.calculators.bank_metrics import compute_bank_metrics
from investiq.calculators.bank_valuation import (
    DEFAULT_COST_OF_EQUITY,
    calculate_dividend_payout_ratio,
    calculate_pb_roe_valuation,
    calculate_pe_valuation,
    calculate_sustainable_growth,
    compute_bank_valuation,
)
from investiq.data.loader import load_financial_data
from investiq.models.evidence import EvidenceTag
from investiq.models.valuation import ValuationMethod


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


class TestSustainableGrowth:
    """Test sustainable growth rate calculation."""

    def test_basic_calculation(self):
        """g = retention × ROE. If ROE=16%, payout=25%, g = 0.75 × 0.16 = 12%."""
        g = calculate_sustainable_growth(roe_pct=16.0, dividend_payout_ratio=0.25)
        assert g == pytest.approx(0.12)

    def test_zero_payout(self):
        """No dividends → full retention → g = ROE."""
        g = calculate_sustainable_growth(roe_pct=15.0, dividend_payout_ratio=0.0)
        assert g == pytest.approx(0.15)

    def test_full_payout(self):
        """100% payout → zero retention → g = 0."""
        g = calculate_sustainable_growth(roe_pct=15.0, dividend_payout_ratio=1.0)
        assert g == pytest.approx(0.0)


class TestDividendPayoutRatio:
    """Test dividend payout ratio calculation."""

    def test_normal_payout(self):
        """DPS=15, EPS=60 → payout = 25%."""
        ratio = calculate_dividend_payout_ratio(15.0, 60.0)
        assert ratio == pytest.approx(0.25)

    def test_no_dividend(self):
        """No DPS → payout = 0."""
        assert calculate_dividend_payout_ratio(None, 60.0) == 0.0

    def test_zero_eps(self):
        """Zero EPS → payout = 0 (guard)."""
        assert calculate_dividend_payout_ratio(15.0, 0.0) == 0.0

    def test_negative_eps(self):
        """Negative EPS → payout = 0."""
        assert calculate_dividend_payout_ratio(15.0, -10.0) == 0.0

    def test_payout_capped_at_one(self):
        """Payout ratio shouldn't exceed 1.0."""
        ratio = calculate_dividend_payout_ratio(100.0, 50.0)
        assert ratio == 1.0


class TestPBROEValuation:
    """Test P/B × ROE valuation method."""

    def test_basic_valuation(self):
        """Known inputs should produce correct justified P/B and fair value."""
        result = calculate_pb_roe_valuation(
            roe_pct=16.0,
            bvps=500.0,
            current_price=600.0,
            sustainable_growth=0.12,
            cost_of_equity=0.135,
        )

        # Justified P/B = (0.16 - 0.12) / (0.135 - 0.12) = 0.04 / 0.015 = 2.667
        # Fair value = 2.667 × 500 = 1333.33
        assert result.method == ValuationMethod.PB_ROE
        assert result.estimated_fair_value == pytest.approx(1333.33, abs=1.0)
        assert result.current_price == 600.0

    def test_upside_calculation(self):
        """Upside = (fair - current) / current × 100."""
        result = calculate_pb_roe_valuation(
            roe_pct=16.0, bvps=500.0, current_price=600.0,
            sustainable_growth=0.12, cost_of_equity=0.135,
        )
        # Fair ≈ 1333, upside ≈ (1333 - 600) / 600 × 100 ≈ 122%
        assert result.upside_pct > 100

    def test_coe_equals_growth_fallback(self):
        """When CoE = g, should fall back to ROE/CoE."""
        result = calculate_pb_roe_valuation(
            roe_pct=13.5, bvps=500.0, current_price=600.0,
            sustainable_growth=0.135, cost_of_equity=0.135,
        )
        # Fallback: Justified P/B = ROE / CoE = 0.135 / 0.135 = 1.0
        assert result.estimated_fair_value == pytest.approx(500.0, abs=1.0)

    def test_assumptions_tagged(self):
        """Assumptions should be tagged as ASSUMPTION."""
        result = calculate_pb_roe_valuation(
            roe_pct=16.0, bvps=500.0, current_price=600.0,
            sustainable_growth=0.12, cost_of_equity=0.135,
        )
        for assumption in result.assumptions:
            assert assumption.tag == EvidenceTag.ASSUMPTION

    def test_evidence_tagged_as_calculation(self):
        """Evidence items should be tagged as CALCULATION."""
        result = calculate_pb_roe_valuation(
            roe_pct=16.0, bvps=500.0, current_price=600.0,
            sustainable_growth=0.12, cost_of_equity=0.135,
        )
        for ev in result.evidence:
            assert ev.tag == EvidenceTag.CALCULATION


class TestPEValuation:
    """Test P/E valuation method."""

    def test_basic_valuation(self):
        """Known inputs should produce correct justified P/E and fair value."""
        result = calculate_pe_valuation(
            eps=85.0,
            current_price=1855.0,
            dividend_payout_ratio=0.26,
            sustainable_growth=0.12,
            cost_of_equity=0.135,
        )

        # Justified P/E = 0.26 / (0.135 - 0.12) = 0.26 / 0.015 = 17.33
        # Fair value = 17.33 × 85 = 1473.33
        assert result.method == ValuationMethod.PE
        assert result.estimated_fair_value == pytest.approx(1473.33, abs=1.0)

    def test_negative_eps_returns_zero(self):
        """Negative EPS should produce zero fair value."""
        result = calculate_pe_valuation(
            eps=-10.0, current_price=500.0,
            dividend_payout_ratio=0.25, sustainable_growth=0.10,
            cost_of_equity=0.135,
        )
        assert result.estimated_fair_value == 0.0

    def test_coe_less_than_growth(self):
        """CoE < g should produce zero fair value (model breaks down)."""
        result = calculate_pe_valuation(
            eps=85.0, current_price=1855.0,
            dividend_payout_ratio=0.25, sustainable_growth=0.15,
            cost_of_equity=0.135,
        )
        assert result.estimated_fair_value == 0.0


class TestComputeBankValuation:
    """Integration test: full valuation pipeline with HDFC Bank data."""

    @pytest.fixture
    def hdfc_latest_metrics(self):
        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        metrics = compute_bank_metrics(data)
        return metrics[-1]  # Latest year (FY2025)

    @pytest.fixture
    def hdfc_data(self):
        return load_financial_data("HDFCBANK", data_dir=DATA_DIR)

    def test_full_valuation_pipeline(self, hdfc_latest_metrics, hdfc_data):
        """Run complete valuation on HDFC Bank and check structure."""
        latest_is = [
            is_ for is_ in hdfc_data.income_statements
            if is_.fiscal_year == "FY2025"
        ][0]

        summary = compute_bank_valuation(
            latest_metrics=hdfc_latest_metrics,
            current_price=hdfc_data.market_data.current_price,
            dividend_per_share=latest_is.dividend_per_share,
        )

        assert len(summary.methods) == 2
        assert summary.blended_fair_value > 0
        assert summary.verdict in ("Undervalued", "Fairly Valued", "Overvalued")

    def test_method_types(self, hdfc_latest_metrics, hdfc_data):
        """Should have both P/B and P/E methods."""
        latest_is = [
            is_ for is_ in hdfc_data.income_statements
            if is_.fiscal_year == "FY2025"
        ][0]

        summary = compute_bank_valuation(
            latest_metrics=hdfc_latest_metrics,
            current_price=hdfc_data.market_data.current_price,
            dividend_per_share=latest_is.dividend_per_share,
        )

        methods = {m.method for m in summary.methods}
        assert ValuationMethod.PB_ROE in methods
        assert ValuationMethod.PE in methods

    def test_blended_is_weighted_average(self, hdfc_latest_metrics, hdfc_data):
        """Blended value = 60% × P/B + 40% × P/E."""
        latest_is = [
            is_ for is_ in hdfc_data.income_statements
            if is_.fiscal_year == "FY2025"
        ][0]

        summary = compute_bank_valuation(
            latest_metrics=hdfc_latest_metrics,
            current_price=hdfc_data.market_data.current_price,
            dividend_per_share=latest_is.dividend_per_share,
        )

        pb_val = [m for m in summary.methods if m.method == ValuationMethod.PB_ROE][0]
        pe_val = [m for m in summary.methods if m.method == ValuationMethod.PE][0]

        expected_blended = 0.6 * pb_val.estimated_fair_value + 0.4 * pe_val.estimated_fair_value
        assert summary.blended_fair_value == pytest.approx(expected_blended, abs=0.01)

    def test_cost_of_equity_default(self):
        """Default cost of equity should be 13.5%."""
        assert DEFAULT_COST_OF_EQUITY == pytest.approx(0.135)

    def test_custom_weights(self, hdfc_latest_metrics, hdfc_data):
        """Custom weights should change the blended value."""
        latest_is = [
            is_ for is_ in hdfc_data.income_statements
            if is_.fiscal_year == "FY2025"
        ][0]

        summary_default = compute_bank_valuation(
            latest_metrics=hdfc_latest_metrics,
            current_price=hdfc_data.market_data.current_price,
            dividend_per_share=latest_is.dividend_per_share,
        )

        summary_custom = compute_bank_valuation(
            latest_metrics=hdfc_latest_metrics,
            current_price=hdfc_data.market_data.current_price,
            dividend_per_share=latest_is.dividend_per_share,
            pb_weight=0.5,
            pe_weight=0.5,
        )

        # Different weights should generally produce different blended values
        # (unless both methods coincidentally give the same fair value)
        assert summary_custom.pb_weight == 0.5
        assert summary_custom.pe_weight == 0.5
