"""Unit tests for the reporting layer.

Uses mock report data without live BigQuery.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from investiq.reporting import render_report
from investiq.reporting.data import ReportData
from investiq.reporting.charts import render_all_metric_charts
from investiq.reporting.report import (
    _compute_upside,
    _build_thesis_groups,
    _build_analyst_intelligence,
    _build_scenario_cards,
    _build_evidence_summary,
    _build_history_timeline,
    _is_model_evidence,
    _clean_evidence_label,
)


def _make_report_data(
    ticker: str = "TESTCORP",
    company_name: str = "Test Corporation Ltd",
    current_price: float | None = 150.0,
    blended_fair_value: float | None = 200.0,
    has_metrics: bool = True,
    has_findings: bool = True,
    has_evidence: bool = True,
    has_scenarios: bool = True,
    has_thesis: bool = True,
    has_history: bool = False,
) -> ReportData:
    snap_id = "test-snap-001"
    return ReportData(
        snapshot_id=snap_id, ticker=ticker,
        company_name=company_name, sector="Financial Services",
        company_type="BANK",
        generated_at=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
        current_price=current_price, blended_fair_value=blended_fair_value,
        valuation_verdict="Undervalued", overall_assessment="Conviction Buy",
        executive_summary="Strong bank with durable moat.",
        investment_thesis="Well-positioned for sustained growth.",
        num_findings=3, num_metrics_years=3,
        thesis_items=pd.DataFrame([
            {"snapshot_id": snap_id, "ticker": ticker, "item_type": "STRENGTH", "item_text": "Strong deposit franchise"},
            {"snapshot_id": snap_id, "ticker": ticker, "item_type": "RISK", "item_text": "Regulatory changes"},
            {"snapshot_id": snap_id, "ticker": ticker, "item_type": "UNKNOWN_TYPE", "item_text": "Custom item"},
        ]) if has_thesis else pd.DataFrame(),
        metrics=pd.DataFrame([
            {"snapshot_id": snap_id, "ticker": ticker,
             "fiscal_year": "FY2024", "roe": 15.0, "roa": 1.5, "nim": 3.5,
             "casa_ratio": 35.0, "cost_to_income": 45.0,
             "gross_npa_ratio": 1.2, "net_npa_ratio": 0.4,
             "eps": 80.0, "bvps": 500.0, "credit_cost": 0.5},
            {"snapshot_id": snap_id, "ticker": ticker,
             "fiscal_year": "FY2025", "roe": 16.0, "roa": 1.6, "nim": 3.6,
             "casa_ratio": 36.0, "cost_to_income": 44.0,
             "gross_npa_ratio": 1.1, "net_npa_ratio": 0.3,
             "eps": 85.0, "bvps": 520.0, "credit_cost": 0.4},
            {"snapshot_id": snap_id, "ticker": ticker,
             "fiscal_year": "FY2026", "roe": 17.0, "roa": 1.7, "nim": 3.7,
             "casa_ratio": 37.0, "cost_to_income": 43.0,
             "gross_npa_ratio": 1.0, "net_npa_ratio": 0.2,
             "eps": 90.0, "bvps": 540.0, "credit_cost": 0.3},
        ]) if has_metrics else pd.DataFrame(),
        findings=pd.DataFrame([
            {"snapshot_id": snap_id, "ticker": ticker,
             "analyst": "Financial Analyst", "category": "profitability",
             "title": "Strong NIM", "statement": "Well-managed NIM.",
             "confidence": 0.90,
             "fundamental_observation": "Consistent margin expansion.",
             "why_it_matters": "Drives profitability.",
             "positive_implication": "Above-peer NIM.",
             "negative_implication": None,
             "thesis_breaker": "Rate cut cycle.",
             "evidence_ids": ["ev-001"]},
        ]) if has_findings else pd.DataFrame(),
        evidence=pd.DataFrame([
            {"snapshot_id": snap_id, "ticker": ticker,
             "evidence_id": "ev-001", "domain": "FINANCIAL",
             "tag": "CALCULATION", "source": "Annual Report 2025",
             "source_field": "NIM", "source_url": "https://example.com/report",
             "publication_date": "2025-04-01",
             "label": "NIM Trend", "value": "3.6%"},
        ]) if has_evidence else pd.DataFrame(),
        scenarios=pd.DataFrame([
            {"snapshot_id": snap_id, "ticker": ticker,
             "scenario": "BULL", "description": "Strong growth scenario."},
            {"snapshot_id": snap_id, "ticker": ticker,
             "scenario": "BASE", "description": "Base case scenario."},
        ]) if has_scenarios else pd.DataFrame(),

        history=pd.DataFrame([
            {"snapshot_id": "test-snap-000", "ticker": ticker,
             "company_name": company_name, "sector": "Financial Services",
             "company_type": "BANK",
             "generated_at": datetime(2025, 10, 1, 8, 0, tzinfo=timezone.utc),
             "current_price": 140.0, "blended_fair_value": 180.0,
             "valuation_verdict": "Undervalued",
             "overall_assessment": "Conviction Buy",
             "executive_summary": None, "investment_thesis": None,
             "num_findings": 2, "num_metrics_years": 2},
        ]) if has_history else pd.DataFrame(),
    )

class TestReportIntegration:
    def test_report_renders_with_all_data(self):
        data = _make_report_data()
        html = render_report(data)
        assert data.company_name in html
        assert data.ticker in html
        assert data.overall_assessment in html
        assert data.executive_summary in html
        assert data.investment_thesis in html
        assert "150.00" in html
        assert "200.00" in html
        for section in ["Executive Summary", "Investment Thesis",
                         "Thesis at a Glance", "Financial Intelligence",
                         "Analyst Intelligence", "Scenario Analysis",
                         "Evidence Trail"]:
            assert section in html

    def test_report_with_minimal_data(self):
        data = _make_report_data(has_metrics=False, has_findings=False,
                                 has_evidence=False, has_scenarios=False,
                                 has_thesis=False)
        html = render_report(data)
        assert data.company_name in html

class TestUpsideCalculation:
    def test_positive(self):
        assert abs(_compute_upside(100.0, 150.0) - 50.0) < 0.01
    def test_negative(self):
        assert abs(_compute_upside(100.0, 80.0) - (-20.0)) < 0.01
    def test_null_price(self):
        assert _compute_upside(None, 100.0) is None
    def test_null_fair_value(self):
        assert _compute_upside(100.0, None) is None
    def test_zero_price(self):
        assert _compute_upside(0.0, 100.0) is None


class TestThesisGroups:
    def test_known_types(self):
        df = pd.DataFrame([{"snapshot_id":"s1","ticker":"T","item_type":"STRENGTH","item_text":"S1"},{"snapshot_id":"s1","ticker":"T","item_type":"RISK","item_text":"R1"}])
        groups = _build_thesis_groups(df)
        assert len(groups) == 2
        assert groups[0]["label"] == "Key Strength"
        assert groups[0]["bullet_points"] == ["S1"]
        assert groups[1]["label"] == "Risk"
        assert groups[1]["bullet_points"] == ["R1"]
    def test_unknown_types_preserved(self):
        df = pd.DataFrame([{"snapshot_id":"s1","ticker":"T","item_type":"CUSTOM","item_text":"C1"}])
        groups = _build_thesis_groups(df)
        assert "CUSTOM" in groups[0]["label"].upper()
        assert groups[0]["bullet_points"] == ["C1"]
    def test_empty(self):
        assert _build_thesis_groups(pd.DataFrame()) == []


class TestAnalystGroups:
    def test_grouping(self):
        df = pd.DataFrame([{"snapshot_id":"s1","ticker":"T","analyst":"AA","title":"F1","confidence":0.9,"statement":"S1","fundamental_observation":"O1","why_it_matters":"W1","positive_implication":"P1","negative_implication":"N1","thesis_breaker":"TB1","category":"g"},{"snapshot_id":"s1","ticker":"T","analyst":"BB","title":"F2","confidence":0.8,"statement":"S2","category":"r","fundamental_observation":None,"why_it_matters":None,"positive_implication":None,"negative_implication":None,"thesis_breaker":None}])
        findings = _build_analyst_intelligence(df)
        assert len(findings) == 2
        assert findings[0]["analyst"] == "AA"
        assert findings[1]["analyst"] == "BB"
        assert findings[0]["confidence_label"] == "High"
        assert findings[1]["confidence_label"] == "High"
    def test_empty(self):
        assert _build_analyst_intelligence(pd.DataFrame()) == []


class TestScenarioCards:
    def test_styles(self):
        df = pd.DataFrame([{"snapshot_id":"s1","ticker":"T","scenario":"BULL","description":"B"},{"snapshot_id":"s1","ticker":"T","scenario":"Bear","description":"Be"},{"snapshot_id":"s1","ticker":"T","scenario":"X","description":"C"}])
        cards = _build_scenario_cards(df)
        assert cards[0]["css_class"] == "bull"
        assert cards[1]["css_class"] == "bear"
        assert cards[2]["css_class"] == ""
    def test_empty(self):
        assert _build_scenario_cards(pd.DataFrame()) == []


class TestEvidenceSummary:
    def test_url(self):
        df = pd.DataFrame([{"snapshot_id":"s1","ticker":"T","evidence_id":"ev-1","domain":"FIN","tag":"CALC","source":"AR","source_url":"https://example.com","label":"L","value":"3.5"}])
        groups = _build_evidence_summary(df)
        assert len(groups) == 1
        assert groups[0]["domain"] == "FIN"
        assert groups[0]["list"][0]["source_url"] == "https://example.com"
    def test_empty(self):
        assert _build_evidence_summary(pd.DataFrame()) == []


class TestHistoryTimeline:
    def test_built(self):
        data = _make_report_data(has_history=True)
        entries = _build_history_timeline(data.history)
        assert len(entries) == 1
        assert "generated_at" in entries[0]
    def test_empty(self):
        assert _build_history_timeline(pd.DataFrame()) == []

class TestEvidenceDeduplication:
    """Tests for evidence canonicalization and deduplication.

    The main evidence view must NOT show model/calculator outputs.
    """

    def test_canonicalize_roe_variations(self):
        from investiq.reporting.report import _canonicalize_evidence_label
        assert _canonicalize_evidence_label("ROE") == "ROE"
        assert _canonicalize_evidence_label("Return on Equity (ROE)") == "ROE"

    def test_canonicalize_unknown(self):
        from investiq.reporting.report import _canonicalize_evidence_label
        assert _canonicalize_evidence_label("UNIQUE_METRIC") == "UNIQUE_METRIC"

    def test_is_model_evidence_calculator_source(self):
        assert _is_model_evidence("ROE", "InvestIQ Calculator", None) is True
        assert _is_model_evidence("ROE", "Annual Report", None) is False

    def test_is_model_evidence_justified_pb(self):
        assert _is_model_evidence("Justified P/B", "InvestIQ Model", None) is True

    def test_is_model_evidence_justified_pe(self):
        assert _is_model_evidence("Justified P/E", "InvestIQ Model", None) is True

    def test_is_model_evidence_sgr(self):
        assert _is_model_evidence("Sustainable Growth Rate", "Model", None) is True

    def test_is_model_evidence_cos_of_equity(self):
        assert _is_model_evidence("Cost of Equity", "Model", None) is True

    def test_is_model_evidence_dividend_payout(self):
        assert _is_model_evidence("Dividend Payout Ratio", "Model", None) is True

    def test_is_model_evidence_fair_value(self):
        assert _is_model_evidence("Fair Value", "Model", None) is True

    def test_is_model_evidence_formula(self):
        """Primary-source formula evidence (with =) is NOT model evidence."""
        assert _is_model_evidence("ROE = Net Profit / Equity", "Financial Statements", None) is False
        assert _is_model_evidence("NIM = NII / Avg Total Assets = 3.27%", "Annual Report 2025", None) is False
        assert _is_model_evidence("CASA Ratio = CASA / Total Deposits = 34.96%", "Company Filing", None) is False

    def test_is_model_evidence_financial_metric(self):
        assert _is_model_evidence("ROE", "Financial Statements FY2025", None) is False
        assert _is_model_evidence("CASA Ratio", "Annual Report 2025", None) is False
        assert _is_model_evidence("Gross NPA", "Company Filing", None) is False

    def test_clean_evidence_label(self):
        assert _clean_evidence_label("ROE = Net Profit / Avg Equity = 15.42%") == "ROE"
        assert _clean_evidence_label("NIM = NII / Avg Total Assets = 3.27%") == "NIM"
        assert _clean_evidence_label("CASA Ratio = CASA / Total Deposits = 34.96%") == "CASA Ratio"
        assert _clean_evidence_label("Cost-to-Income = Opex / Op Income = 41.51%") == "Cost-to-Income"
        assert _clean_evidence_label("Return on Equity (ROE) FY2025") == "Return on Equity (ROE) FY2025"
        assert _clean_evidence_label("Strong NIM") == "Strong NIM"
        assert _clean_evidence_label(None) == ""
        assert _clean_evidence_label("") == ""

    def test_primary_formula_evidence_retained(self):
        """Primary-source evidence with formula labels must appear in main list."""
        df = pd.DataFrame([
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-1",
             "domain": "FIN", "tag": "CALC", "source": "Financial Statements FY2025",
             "label": "ROE = Net Profit / Avg Equity = 15.42%", "value": "15.42%"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-2",
             "domain": "FIN", "tag": "CALC", "source": "Financial Statements FY2025",
             "label": "NIM = NII / Avg Total Assets = 3.27%", "value": "3.27%"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-3",
             "domain": "FIN", "tag": "CALC", "source": "Financial Statements FY2025",
             "label": "CASA Ratio = CASA / Total Deposits = 34.96%", "value": "34.96%"},
        ])
        groups = _build_evidence_summary(df)
        assert len(groups) == 1
        # All three are primary-source evidence, so all should appear in main list
        assert len(groups[0]["list"]) == 3, f"Expected 3 items in main list, got {len(groups[0]['list'])}"
        # All should also be in detailed
        assert len(groups[0]["all"]) == 3
        # Clean labels should be applied
        for item in groups[0]["list"]:
            assert item["clean_label"] in ("ROE", "NIM", "CASA Ratio"), f"Unexpected clean_label: {item['clean_label']}"

    def test_main_evidence_not_empty_with_valid_data(self):
        """Regression test: main Evidence Trail must NOT be empty when
        valid primary-source evidence exists."""
        df = pd.DataFrame([
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-1",
             "domain": "FINANCIAL", "tag": "CALC", "source": "FY2025 Annual Report",
             "label": "ROE = Net Profit / Avg Equity = 15.42%", "value": "15.42%"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-2",
             "domain": "FINANCIAL", "tag": "CALC", "source": "FY2025 Annual Report",
             "label": "NIM = NII / Avg Total Assets = 3.27%", "value": "3.27%"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-3",
             "domain": "VALUATION", "tag": "", "source": "InvestIQ Model",
             "label": "Justified P/B", "value": "1.5x"},
        ])
        groups = _build_evidence_summary(df)
        total_main = sum(len(g["list"]) for g in groups)
        total_all = sum(len(g["all"]) for g in groups)
        # Main must have at least the 2 FINANCIAL items
        assert total_main >= 2, f"Main evidence trail should have >=2 items, got {total_main}"
        # Detailed must have all 3
        assert total_all == 3, f"Detailed evidence should have 3 items, got {total_all}"

    def test_model_evidence_excluded_from_main(self):
        """Justified P/B, SGR, Cost of Equity etc should NOT appear in main list."""
        df = pd.DataFrame([
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-1",
             "domain": "VALUATION", "tag": "", "source": "InvestIQ Model",
             "label": "Justified P/B", "value": "1.5x"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-2",
             "domain": "VALUATION", "tag": "", "source": "InvestIQ Model",
             "label": "Sustainable Growth Rate", "value": "8.2%"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-3",
             "domain": "VALUATION", "tag": "", "source": "InvestIQ Model",
             "label": "Cost of Equity", "value": "10.5%"},
        ])
        groups = _build_evidence_summary(df)
        assert len(groups) == 1
        assert len(groups[0]["list"]) == 0, "Model evidence must NOT be in main list"
        assert len(groups[0]["all"]) == 3, "Model evidence must be preserved in detailed"

    def test_dedup_same_metric(self):
        """Calculator-derived ROE should not appear in main view."""
        df = pd.DataFrame([
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-1",
             "domain": "FIN", "tag": "CALC", "source": "Annual Report 2025",
             "label": "ROE", "value": "15.42%"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-2",
             "domain": "FIN", "tag": "Calculator", "source": "InvestIQ Calc",
             "label": "Return on Equity (ROE)", "value": "15.42%"},
        ])
        groups = _build_evidence_summary(df)
        assert len(groups) == 1
        # Main list should only have the Annual Report item (calculator is model)
        assert len(groups[0]["list"]) == 1
        assert groups[0]["list"][0]["source"] == "Annual Report 2025"
        # Detailed should have both
        assert len(groups[0]["all"]) == 2

    def test_different_values_not_merged(self):
        """Materially different source values must both appear in main view."""
        df = pd.DataFrame([
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-1",
             "domain": "FIN", "tag": "", "source": "Source A",
             "label": "NIM", "value": "3.27"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-2",
             "domain": "FIN", "tag": "", "source": "Source B",
             "label": "NIM", "value": "3.48"},
        ])
        groups = _build_evidence_summary(df)
        assert len(groups[0]["list"]) == 2
        assert len(groups[0]["all"]) == 2
class TestHistoryDeduplication:
    """Tests for snapshot deduplication in research history."""

    def test_single_snapshot(self):
        df = pd.DataFrame([{"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None}])
        assert len(_build_history_timeline(df)) == 1

    def test_two_distinct(self):
        df = pd.DataFrame([{"snapshot_id": "s2", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 110.0, "blended_fair_value": 130.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None},
            {"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None}])
        entries = _build_history_timeline(df)
        assert len(entries) == 2
        assert "changes" in entries[0] or "no_changes" in entries[0]

    def test_duplicates_suppressed(self):
        df = pd.DataFrame([{"snapshot_id": "s3", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None},
            {"snapshot_id": "s2", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 20, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None},
            {"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None}])
        assert len(_build_history_timeline(df)) == 1

    def test_max_two(self):
        df = pd.DataFrame([{"snapshot_id": "s4", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 130.0, "blended_fair_value": 150.0,
            "valuation_verdict": "Great", "overall_assessment": "Strong",
            "executive_summary": "S4", "investment_thesis": "I4"},
            {"snapshot_id": "s3", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 120.0, "blended_fair_value": 140.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": "S3", "investment_thesis": "I3"},
            {"snapshot_id": "s2", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 120.0, "blended_fair_value": 140.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": "S3", "investment_thesis": "I3"},
            {"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": "S1", "investment_thesis": "I1"}])
        entries = _build_history_timeline(df)
        assert len(entries) <= 2
        assert entries[0]["current_price"] == 130.0

    def test_no_changes_flag(self):
        df = pd.DataFrame([{"snapshot_id": "s2", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None},
            {"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None}])
        entries = _build_history_timeline(df)
        assert len(entries) == 1, "Expected 1 (identical content deduped)"
    """Tests for snapshot deduplication in research history."""

    def test_single_snapshot(self):
        df = pd.DataFrame([{"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None}])
        assert len(_build_history_timeline(df)) == 1

    def test_two_distinct(self):
        df = pd.DataFrame([{"snapshot_id": "s2", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 110.0, "blended_fair_value": 130.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None},
            {"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None}])
        entries = _build_history_timeline(df)
        assert len(entries) == 2
        assert "changes" in entries[0] or "no_changes" in entries[0]

    def test_duplicates_suppressed(self):
        df = pd.DataFrame([{"snapshot_id": "s3", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None},
            {"snapshot_id": "s2", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 20, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None},
            {"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None}])
        assert len(_build_history_timeline(df)) == 1

    def test_max_two(self):
        df = pd.DataFrame([{"snapshot_id": "s4", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 130.0, "blended_fair_value": 150.0,
            "valuation_verdict": "Great", "overall_assessment": "Strong",
            "executive_summary": "S4", "investment_thesis": "I4"},
            {"snapshot_id": "s3", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 120.0, "blended_fair_value": 140.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": "S3", "investment_thesis": "I3"},
            {"snapshot_id": "s2", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 120.0, "blended_fair_value": 140.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": "S3", "investment_thesis": "I3"},
            {"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": "S1", "investment_thesis": "I1"}])
        entries = _build_history_timeline(df)
        assert len(entries) <= 2
        assert entries[0]["current_price"] == 130.0

    def test_no_changes_flag(self):
        df = pd.DataFrame([{"snapshot_id": "s2", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None},
            {"snapshot_id": "s1", "ticker": "T", "company_name": "TC",
            "generated_at": datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            "current_price": 100.0, "blended_fair_value": 120.0,
            "valuation_verdict": "Good", "overall_assessment": "Positive",
            "executive_summary": None, "investment_thesis": None}])
        entries = _build_history_timeline(df)
        assert len(entries) == 1, f"Expected 1 (identical content deduped)"

    def test_different_values_not_merged(self):
        df = pd.DataFrame([
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-1",
             "domain": "FIN", "tag": "", "source": "Source A",
             "label": "NIM", "value": "3.27"},
            {"snapshot_id": "s1", "ticker": "T", "evidence_id": "ev-2",
             "domain": "FIN", "tag": "", "source": "Source B",
             "label": "NIM", "value": "3.48"},
        ])
        groups = _build_evidence_summary(df)
        assert len(groups[0]["list"]) == 2
        assert len(groups[0]["all"]) == 2

class TestMultipleTickers:
    def test_two_tickers(self):
        a = _make_report_data(ticker="BANK_A", company_name="Bank A Ltd")
        b = _make_report_data(ticker="BANK_B", company_name="Bank B Ltd")
        assert "BANK_A" in render_report(a)
        assert "BANK_B" in render_report(b)

    def test_no_hardcoded_companies(self):
        import inspect
        for mod_name in ["report","charts","data"]:
            mod = __import__(f"investiq.reporting.{mod_name}", fromlist=[""])
            src = inspect.getsource(mod)
            assert "HDFCBANK" not in src
            assert "ICICIBANK" not in src


class TestCharts:
    """Basic chart rendering tests."""

    def test_charts_render_with_metrics(self):
        data = _make_report_data()
        charts = render_all_metric_charts(data.metrics)
        assert len(charts) == 7
        for c in charts:
            assert isinstance(c, str)

    def test_charts_with_empty_df(self):
        charts = render_all_metric_charts(pd.DataFrame())
        assert len(charts) == 7
        # All should be "unavailable" messages
        for c in charts:
            assert "unavailable" in c

    def test_charts_with_partial_metrics(self):
        df = pd.DataFrame([
            {"snapshot_id": "s1", "ticker": "T", "fiscal_year": "FY2024",
             "roe": 15.0, "roa": 1.5, "nim": None,
             "casa_ratio": None, "cost_to_income": None,
             "gross_npa_ratio": None, "net_npa_ratio": None,
             "eps": None, "bvps": None, "credit_cost": None},
        ])
        charts = render_all_metric_charts(df)
        # ROE/ROA should have data; others should not
        assert "unavailable" not in charts[0]  # roe_roa_chart
        for c in charts[1:]:
            assert "unavailable" in c

    def test_missing_thesis(self):
        html = render_report(_make_report_data(has_thesis=False))
        assert "Test Corporation" in html

    def test_missing_metrics(self):
        html = render_report(_make_report_data(has_metrics=False))
        assert "Test Corporation" in html

    def test_missing_findings(self):
        html = render_report(_make_report_data(has_findings=False))
        assert "Test Corporation" in html

    def test_missing_evidence(self):
        html = render_report(_make_report_data(has_evidence=False))
        assert "Test Corporation" in html

    def test_missing_scenarios(self):
        html = render_report(_make_report_data(has_scenarios=False))
        assert "Test Corporation" in html

    def test_null_price(self):
        data = _make_report_data(current_price=None, blended_fair_value=None)
        assert "N/A" in render_report(data)

    def test_zero_price(self):
        data = _make_report_data(current_price=0.0, blended_fair_value=100.0)
        assert "N/A" in render_report(data)
