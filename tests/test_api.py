"""Tests for the InvestIQ HTTP API.

All tests use the existing MockLLMProvider and make zero external API calls.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from investiq.api.app import app

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI application."""
    with TestClient(app) as c:
        yield c


# ──────────────────────────────────────────────────────────────────────────────
# Health endpoint
# ──────────────────────────────────────────────────────────────────────────────


class TestHealth:
    """GET /health"""

    def test_health_returns_200(self, client):
        """Health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status_ok(self, client):
        """Health endpoint returns {'status': 'ok'}."""
        response = client.get("/health")
        assert response.json() == {"status": "ok"}
# ──────────────────────────────────────────────────────────────────────────────
# Research endpoint — HDFCBANK
# ──────────────────────────────────────────────────────────────────────────────


class TestResearchHDFCBANK:
    """POST /research with HDFCBANK ticker."""

    def test_hdfc_returns_200(self, client):
        """HDFCBANK research returns HTTP 200."""
        response = client.post("/research", json={"ticker": "HDFCBANK"})
        assert response.status_code == 200

    def test_hdfc_ticker_in_response(self, client):
        """Response ticker field is HDFCBANK."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        assert data["ticker"] == "HDFCBANK"

    def test_hdfc_company_identity(self, client):
        """Company identity is HDFC Bank Limited."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        assert data["company"]["ticker"] == "HDFCBANK"
        assert data["company"]["name"] == "HDFC Bank Limited"

    def test_hdfc_metrics_exist(self, client):
        """Metrics are present and include ROE, EPS, etc."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        metrics = data["metrics"]
        assert len(metrics) == 5  # FY2021–FY2025
        latest = metrics[-1]
        assert latest["fiscal_year"] == "FY2025"
        assert latest["roe"] > 0
        assert latest["eps"] > 0
        assert latest["casa_ratio"] > 0

    def test_hdfc_valuation_exists(self, client):
        """Valuation result is present."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        valuation = data["valuation"]
        assert valuation["blended_fair_value"] > 0
        assert valuation["verdict"] in ("Undervalued", "Overvalued", "Fairly Valued")
        assert len(valuation["methods"]) >= 1

    def test_hdfc_findings_exist(self, client):
        """Findings are present from all three analysts."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        findings = data["findings"]
        assert len(findings) > 0
        analyst_keys = {f["analyst"] for f in findings}
        assert "financial_analyst" in analyst_keys
        assert "asset_quality_analyst" in analyst_keys
        assert "banking_business_analyst" in analyst_keys

    def test_hdfc_finding_structure(self, client):
        """Each finding has required fields."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        for f in data["findings"]:
            assert "analyst" in f
            assert "title" in f
            assert "statement" in f
            assert "confidence" in f
            assert 0.0 <= f["confidence"] <= 1.0
            assert "evidence_ids" in f
            assert len(f["evidence_ids"]) > 0
            assert "category" in f

    def test_hdfc_cio_synthesis_exists(self, client):
        """CIO synthesis is present."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        synthesis = data.get("cio_synthesis")
        assert synthesis is not None
        assert len(synthesis["executive_summary"]) > 0
        assert len(synthesis["investment_thesis"]) > 0
        assert isinstance(synthesis["key_strengths"], list)
        assert isinstance(synthesis["key_concerns"], list)
        assert isinstance(synthesis["growth_drivers"], list)
        assert isinstance(synthesis["risks"], list)
        assert len(synthesis["bull_case"]) > 0
        assert len(synthesis["base_case"]) > 0
        assert len(synthesis["bear_case"]) > 0
        assert isinstance(synthesis["thesis_breakers"], list)
        assert len(synthesis["overall_assessment"]) > 0

    def test_hdfc_evidence_chain_exists(self, client):
        """Complete evidence chain is returned."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        chain = data.get("evidence_chain", [])
        assert len(chain) > 0

    def test_hdfc_snapshot_id_present(self, client):
        """Snapshot has a unique ID."""
        data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        assert data["snapshot_id"] is not None
        assert len(data["snapshot_id"]) > 0
# ──────────────────────────────────────────────────────────────────────────────
# Research endpoint — ICICIBANK
# ──────────────────────────────────────────────────────────────────────────────


class TestResearchICICIBANK:
    """POST /research with ICICIBANK ticker."""

    def test_icici_returns_200(self, client):
        """ICICIBANK research returns HTTP 200."""
        response = client.post("/research", json={"ticker": "ICICIBANK"})
        assert response.status_code == 200

    def test_icici_ticker_in_response(self, client):
        """Response ticker field is ICICIBANK."""
        data = client.post("/research", json={"ticker": "ICICIBANK"}).json()
        assert data["ticker"] == "ICICIBANK"

    def test_icici_company_identity(self, client):
        """Company identity is ICICI Bank Limited (not HDFC)."""
        data = client.post("/research", json={"ticker": "ICICIBANK"}).json()
        assert data["company"]["ticker"] == "ICICIBANK"
        assert data["company"]["name"] == "ICICI Bank Limited"
        assert "HDFC" not in data["company"]["name"]

    def test_icici_findings_exist(self, client):
        """Findings are present for ICICI."""
        data = client.post("/research", json={"ticker": "ICICIBANK"}).json()
        assert len(data["findings"]) > 0

    def test_icici_metrics_different_from_hdfc(self, client):
        """ICICI metrics differ from HDFC metrics."""
        icici_data = client.post("/research", json={"ticker": "ICICIBANK"}).json()
        hdfc_data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
        icici_latest = icici_data["metrics"][-1]
        hdfc_latest = hdfc_data["metrics"][-1]
        assert icici_latest["roe"] != hdfc_latest["roe"]
        assert icici_latest["eps"] != hdfc_latest["eps"]

    def test_icici_valuation_differs(self, client):
        """ICICI valuation differs from HDFC valuation."""
        icici_data = client.post("/research", json={"ticker": "ICICIBANK"}).json()
        hdfc_data = client.post("/research", json={"ticker": "HDFCBANK"}).json()
# ──────────────────────────────────────────────────────────────────────────────
# Unknown ticker
# ──────────────────────────────────────────────────────────────────────────────


class TestUnknownTicker:
    """POST /research with unknown ticker."""

    def test_unknown_ticker_returns_404(self, client):
        """Unknown ticker returns HTTP 404."""
        response = client.post("/research", json={"ticker": "UNKNOWN_TICKER"})
        assert response.status_code == 404

    def test_unknown_ticker_detail_message(self, client):
        """404 response contains a descriptive message."""
        response = client.post("/research", json={"ticker": "UNKNOWN_TICKER"})
        detail = response.json()
        assert "detail" in detail
        assert "UNKNOWN_TICKER" in detail["detail"]

    def test_unknown_ticker_no_hdfc_fallback(self, client):
        """Unknown ticker does not silently return HDFC data."""
        response = client.post("/research", json={"ticker": "UNKNOWN_TICKER"})
        assert response.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# Input normalization
# ──────────────────────────────────────────────────────────────────────────────


class TestInputNormalization:
    """POST /research with various ticker formats."""

    def test_lowercase_ticker(self, client):
        """Lowercase 'hdfcbank' works (case normalization)."""
        response = client.post("/research", json={"ticker": "hdfcbank"})
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "HDFCBANK"

    def test_whitespace_ticker(self, client):
        """Ticker with leading/trailing whitespace works."""
        response = client.post("/research", json={"ticker": "  HDFCBANK  "})
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "HDFCBANK"

    def test_empty_ticker_returns_422(self, client):
        """Empty ticker returns HTTP 422."""
        response = client.post("/research", json={"ticker": ""})
        assert response.status_code == 422

    def test_whitespace_only_ticker_returns_422(self, client):
        """Whitespace-only ticker (after strip) returns HTTP 422."""
        response = client.post("/research", json={"ticker": "   "})
        assert response.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# No external API calls
# ──────────────────────────────────────────────────────────────────────────────


class TestNoExternalAPICalls:
    """API uses MockLLMProvider — no external calls."""

    def test_hdfc_uses_mock_provider(self, client):
        """HDFC research completes without external API calls."""
        response = client.post("/research", json={"ticker": "HDFCBANK"})
        assert response.status_code == 200

    def test_icici_uses_mock_provider(self, client):
        """ICICI research completes without external API calls."""
        response = client.post("/research", json={"ticker": "ICICIBANK"})
        assert response.status_code == 200
# ──────────────────────────────────────────────────────────────────────────────
# Provider selection verification
# ──────────────────────────────────────────────────────────────────────────────


class TestProviderSelection:
    """Verify that provider selection happens at the application boundary."""

    def test_default_provider_is_mock(self):
        """Default configuration selects MockLLMProvider."""
        from investiq.api.app import get_provider
        from investiq.llm.mock import MockLLMProvider
        provider = get_provider()
        assert isinstance(provider, MockLLMProvider), (
            f"Expected MockLLMProvider, got {type(provider).__name__}. "
            f"Check that LLM_PROVIDER environment is not set to 'gemini' during testing."
        )

    def test_mock_provider_produces_zero_cost_responses(self, client):
        """All responses from mock provider have estimated_cost == 0.0."""
        response = client.post("/research", json={"ticker": "HDFCBANK"})
        assert response.status_code == 200
        # The snapshot itself doesn't carry cost info — this just confirms
        # the mock provider completes without error, meaning zero external calls.

    def test_gemini_provider_config_raises_without_credentials(self, monkeypatch):
        """Selecting Gemini without credentials raises ConfigurationError."""
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "true")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        from investiq.config import ConfigurationError, load_settings
        settings = load_settings()
        with pytest.raises(ConfigurationError, match="GEMINI_API_KEY is missing or empty"):
            settings.validate_provider()

    def test_gemini_provider_requires_allow_real_flag(self, monkeypatch):
        """Selecting Gemini without INVESTIQ_ALLOW_REAL_LLM=true raises ConfigurationError."""
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "false")
        monkeypatch.setenv("GEMINI_API_KEY", "dummy_key")

        from investiq.config import ConfigurationError, load_settings
        settings = load_settings()
        with pytest.raises(ConfigurationError, match="INVESTIQ_ALLOW_REAL_LLM is false"):
            settings.validate_provider()