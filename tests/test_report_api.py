"""API tests for the /report/{ticker} endpoint.

Uses mock data (no live BigQuery or research pipeline).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from investiq.api.app import app
    return TestClient(app, raise_server_exceptions=False)


class TestReportEndpoint:
    """Tests for GET /report/{ticker}."""

    def test_valid_ticker_returns_html(self, client):
        """A valid ticker should return HTML report."""
        with patch("investiq.reporting.build_report") as mock_build:
            mock_build.return_value = "<html><body><h1>HDFCBANK Report</h1></body></html>"
            resp = client.get("/report/HDFCBANK")
            assert resp.status_code == 200
            assert "text/html" in resp.headers.get("content-type", "")
            assert "HDFCBANK" in resp.text

    def test_unknown_ticker_returns_404(self, client):
        """An unknown ticker should return 404."""
        from investiq.reporting import build_report
        with patch("investiq.reporting.build_report") as mock_build:
            mock_build.side_effect = LookupError("No snapshot found")
            resp = client.get("/report/UNKNOWN_TICKER_XYZ")
            assert resp.status_code == 404

    def test_empty_ticker_returns_422(self, client):
        """An empty ticker should return 422."""
        resp = client.get("/report/ ")
        assert resp.status_code == 422

    def test_investiq_dashboard_returns_html(self, client):
        """GET /investiq/{ticker} should return HTML dashboard."""
        resp = client.get("/investiq/HDFCBANK")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "InvestIQ" in resp.text

    def test_investiq_dashboard_empty_ticker_422(self, client):
        """Empty ticker should return 422."""
        resp = client.get("/investiq/ ")
        assert resp.status_code == 422

    def test_research_api_valid_ticker(self, client):
        """GET /api/v1/research/{ticker} should return JSON."""
        with patch("investiq.reporting.data.ReportDataFetcher.fetch") as mock_fetch:
            from unittest.mock import MagicMock
            mock_data = MagicMock()
            mock_data.snapshot_id = "snap-001"
            mock_data.ticker = "HDFCBANK"
            mock_data.company_name = "HDFC Bank"
            mock_data.sector = "Banking"
            mock_data.company_type = "Private"
            mock_data.generated_at = "08 Sep 2026"
            mock_data.current_price = 1970.0
            mock_data.blended_fair_value = 2250.0
            mock_data.valuation_verdict = "Undervalued"
            mock_data.overall_assessment = "Strong Buy"
            mock_data.executive_summary = "Strong fundamentals"
            mock_data.investment_thesis = "Good growth"
            mock_data.num_findings = 5
            mock_data.num_metrics_years = 3
            mock_data.thesis_items = MagicMock()
            mock_data.thesis_items.empty = True
            mock_data.findings = MagicMock()
            mock_data.findings.empty = True
            mock_data.evidence = MagicMock()
            mock_data.evidence.empty = True
            mock_data.scenarios = MagicMock()
            mock_data.scenarios.empty = True
            mock_data.history = MagicMock()
            mock_data.history.empty = True
            mock_fetch.return_value = mock_data

            resp = client.get("/api/v1/research/HDFCBANK")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ticker"] == "HDFCBANK"
            assert data["company_name"] == "HDFC Bank"
            assert data["current_price"] == 1970.0
            assert data["blended_fair_value"] == 2250.0
            assert data["valuation_verdict"] == "Undervalued"
            assert "upside_pct" in data
            assert data["overall_assessment"] == "Strong Buy"

    def test_research_api_unknown_ticker_404(self, client):
        """Unknown ticker returns 404 with a clear message."""
        with patch("investiq.reporting.data.ReportDataFetcher.fetch") as mock_fetch:
            mock_fetch.side_effect = LookupError("No snapshot found")
            resp = client.get("/api/v1/research/UNKNOWN_TICKER_XYZ")
            assert resp.status_code == 404
            data = resp.json()
            assert "detail" in data
            assert "UNKNOWN_TICKER_XYZ" in data["detail"]

    def test_research_api_empty_ticker_422(self, client):
        """Empty ticker returns 422."""
        resp = client.get("/api/v1/research/ ")
        assert resp.status_code == 422

    def test_no_hardcoded_nvidia_or_apple(self, client):
        """Verify no hardcoded generic stock data in endpoints."""
        resp = client.get("/investiq/ICICIBANK")
        assert resp.status_code == 200
        assert "NVIDIA" not in resp.text
        assert "Apple" not in resp.text
        assert "Tesla" not in resp.text
        assert "Microsoft" not in resp.text
        assert "NVDA" not in resp.text
        assert "AAPL" not in resp.text
        assert "$" not in resp.text  # No US dollar values

    def test_ticker_normalization_strip_upper(self, client):
        """hdfcbank (lowercase) should work like HDFCBANK."""
        with patch("investiq.reporting.build_report") as mock_build:
            mock_build.return_value = "<html><body><h1>HDFCBANK Report</h1></body></html>"
            resp = client.get("/report/hdfcbank")
            assert resp.status_code == 200
            # Verify ticker was normalized to uppercase
            call_args = mock_build.call_args
            assert call_args is not None
            assert call_args[0][0] == "HDFCBANK"


class TestRootRoutes:
    """Tests for root/default routes — should not redirect to HDFCBANK."""

    def test_root_redirects_to_dashboard(self, client):
        """GET / should redirect to the dashboard."""
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/investiq/HDFCBANK" in resp.headers.get("location", "")

    def test_investiq_root_returns_info(self, client):
        """GET /investiq returns usage info, not a redirect."""
        resp = client.get("/investiq")
        assert resp.status_code == 200
        data = resp.json()
        assert "detail" in data
        assert "ticker" in data["detail"]

    def test_report_root_returns_info(self, client):
        """GET /report returns usage info, not a redirect."""
        resp = client.get("/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "detail" in data
        assert "ticker" in data["detail"]

    def test_hdfcbank_dashboard_still_works(self, client):
        """Explicit /investiq/HDFCBANK still returns HTML dashboard."""
        resp = client.get("/investiq/HDFCBANK")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_icicibank_dashboard_still_works(self, client):
        """Explicit /investiq/ICICIBANK still returns HTML dashboard."""
        resp = client.get("/investiq/ICICIBANK")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_hdfcbank_report_still_works(self, client):
        """Explicit /report/HDFCBANK still works."""
        with patch("investiq.reporting.build_report") as mock_build:
            mock_build.return_value = "<html><body><h1>HDFCBANK Report</h1></body></html>"
            resp = client.get("/report/HDFCBANK")
            assert resp.status_code == 200

    def test_icicibank_report_still_works(self, client):
        """Explicit /report/ICICIBANK still works."""
        with patch("investiq.reporting.build_report") as mock_build:
            mock_build.return_value = "<html><body><h1>ICICIBANK Report</h1></body></html>"
            resp = client.get("/report/ICICIBANK")
            assert resp.status_code == 200


class TestMissingTickerHandling:
    """Tests for graceful missing/unsupported ticker handling."""

    def test_research_api_file_not_found(self, client):
        """FileNotFoundError from data loader returns HTTP 404."""
        with patch("investiq.reporting.data.ReportDataFetcher.fetch") as mock_fetch:
            mock_fetch.side_effect = FileNotFoundError("No prepared data for UNKNOWN")
            resp = client.get("/api/v1/research/UNKNOWN")
            assert resp.status_code == 404
            data = resp.json()
            assert "detail" in data
            assert "UNKNOWN" in data["detail"]

    def test_research_api_lookup_error(self, client):
        """LookupError from BigQuery fetcher returns HTTP 404."""
        with patch("investiq.reporting.data.ReportDataFetcher.fetch") as mock_fetch:
            mock_fetch.side_effect = LookupError("No snapshot found for TEST")
            resp = client.get("/api/v1/research/TEST")
            assert resp.status_code == 404
            data = resp.json()
            assert "detail" in data
            assert "TEST" in data["detail"]

    def test_research_api_unexpected_error_not_404(self, client):
        """Unexpected exceptions should NOT be converted to 404."""
        with patch("investiq.reporting.data.ReportDataFetcher.fetch") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("Unexpected database failure")
            resp = client.get("/api/v1/research/HDFCBANK")
            # Should be 500, NOT 404 (RuntimeError is not LookupError or FileNotFoundError)
            assert resp.status_code == 500

    def test_valid_ticker_passes_through(self, client):
        """Valid ticker still returns HTTP 200 with full data."""
        with patch("investiq.reporting.data.ReportDataFetcher.fetch") as mock_fetch:
            from unittest.mock import MagicMock
            mock_data = MagicMock()
            mock_data.snapshot_id = "snap-001"
            mock_data.ticker = "HDFCBANK"
            mock_data.company_name = "HDFC Bank Limited"
            mock_data.sector = "financial_services"
            mock_data.company_type = "BANK"
            mock_data.generated_at = "08 Sep 2026"
            mock_data.current_price = 1970.0
            mock_data.blended_fair_value = 2250.0
            mock_data.valuation_verdict = "Undervalued"
            mock_data.overall_assessment = "Conviction Buy"
            mock_data.executive_summary = "Summary"
            mock_data.investment_thesis = "Thesis"
            mock_data.num_findings = 3
            mock_data.num_metrics_years = 3
            mock_data.thesis_items = MagicMock()
            mock_data.thesis_items.empty = True
            mock_data.findings = MagicMock()
            mock_data.findings.empty = True
            mock_data.evidence = MagicMock()
            mock_data.evidence.empty = True
            mock_data.scenarios = MagicMock()
            mock_data.scenarios.empty = True
            mock_data.history = MagicMock()
            mock_data.history.empty = True
            mock_fetch.return_value = mock_data

            resp = client.get("/api/v1/research/HDFCBANK")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ticker"] == "HDFCBANK"
            assert data["company_name"] == "HDFC Bank Limited"
            assert data["current_price"] == 1970.0
            assert data["blended_fair_value"] == 2250.0
            assert data["valuation_verdict"] == "Undervalued"
            assert "upside_pct" in data
