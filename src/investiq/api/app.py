"""FastAPI application for the InvestIQ research API.

Exposes:
    GET  /health      — Health/readiness check
    POST /research    — Run full research pipeline for a ticker

Delegates all research logic to the existing ResearchOrchestrator.
No research logic is duplicated in this API layer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from investiq.config import load_settings
from investiq.llm.mock import MockLLMProvider
from investiq.research.evidence_fixture import get_synthetic_bank_evidence
from investiq.research.orchestrator import ResearchOrchestrator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "prepared"

settings = load_settings()


# LLM provider is created on each call to get_provider() when settings change.
# This ensures that environment overrides (pytest conftest, monkeypatch)
# are respected regardless of import order.
# The orchestrator, analysts, and CIO are completely provider-agnostic.
_provider = None
_provider_settings_sig = None


def get_provider():
    """Return the appropriate LLM provider for the current configuration.

    Re-reads settings on every call so that pytest environment isolation
    (INVESTIQ_TESTING from conftest) is always respected, even when
    app.py is imported before conftest.py is evaluated.
    """
    global _provider, _provider_settings_sig
    current = load_settings()
    sig = (current.llm_provider, current.gemini_api_key, current.gemini_model,
           current.investiq_allow_real_llm)
    if _provider is not None and _provider_settings_sig == sig:
        return _provider
    if current.llm_provider.lower() == "gemini":
        from investiq.llm.gemini import GeminiProvider

        logger.info(
            "Using GeminiLLMProvider (model=%s, max_calls=%s)",
            current.gemini_model,
            current.max_external_llm_calls,
        )
        _provider = GeminiProvider()
    else:
        logger.info("Using MockLLMProvider (deterministic, zero external API calls)")
        _provider = MockLLMProvider(simulated_latency_ms=0.0)
    _provider_settings_sig = sig
    return _provider


# Initialize BigQuery research repository for persistence.
# Falls back to a no-op FakeBigQueryResearchRepository if BigQuery is not
# configured (e.g., local development, no GCP credentials, mock mode).
# This ensures the API works identically regardless of persistence setup.
try:
    from investiq.storage import BigQueryResearchRepository
    _repository = BigQueryResearchRepository()
    logger.info(
        "BigQuery repository initialized (project=%s, dataset=%s)",
        _repository.project_id, _repository.dataset_id,
    )
except Exception:
    from investiq.storage import FakeBigQueryResearchRepository
    logger.info(
        "BigQuery not configured — using FakeBigQueryResearchRepository. "
        "Snapshots will not be persisted to BigQuery."
    )
    _repository = FakeBigQueryResearchRepository()

# Singleton orchestrator — safe to reuse because orchestration is stateless
# with respect to company data. Each request loads its own FinancialData
# from the ticker-specific JSON file.
_orchestrator: ResearchOrchestrator | None = None


def get_orchestrator() -> ResearchOrchestrator:
    """Return the shared ResearchOrchestrator instance (lazy init)."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ResearchOrchestrator(
            provider=get_provider(),
            data_dir=DATA_DIR,
        )
    return _orchestrator


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="InvestIQ Research API",
    version="0.1.0",
    description="Institutional-style equity research for Indian banking stocks.",
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    """POST /research request body."""

    ticker: str


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    """Translate FileNotFoundError (unknown ticker) into HTTP 404."""
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    """Health/readiness check for Cloud Run.

    Returns a simple status without invoking the research engine.
    """
    return {"status": "ok"}


@app.post("/research")
def research(body: ResearchRequest) -> dict[str, Any]:
    """Run the full research pipeline for a ticker.

    Delegates to the existing ResearchOrchestrator which handles:
        1. Financial data loading
        2. Bank metric calculation
        3. Bank valuation
        4. Evidence collection
        5. Three analyst executions
        6. CIO synthesis

    Returns the complete ResearchSnapshot serialized as JSON.
    """
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=422, detail="Ticker must be a non-empty string.")

    orchestrator = get_orchestrator()

    # Provide synthetic evidence appropriate for the requested ticker.
    evidence_items = get_synthetic_bank_evidence(ticker)

    try:
        snapshot = orchestrator.research(ticker, evidence_items=evidence_items)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Prepared financial data not found for ticker '{ticker}'.",
        )

    # Persist the snapshot to BigQuery (or fake repository if not configured).
    # Persistence failure is logged but does NOT prevent the API response.
    # Research generation is more important than persistence for the hackathon.
    try:
        _repository.save_snapshot(snapshot)
    except Exception:
        logger.exception(
            "BIGQUERY PERSISTENCE FAILED for snapshot %s (ticker=%s). "
            "Research result is still returned to the client.",
            snapshot.snapshot_id, ticker,
        )

    # Serialize the existing Pydantic model directly — no manual reconstruction.
    return snapshot.model_dump(mode="json")


@app.get("/report/{ticker}")
def report(ticker: str) -> HTMLResponse:
    """Generate an interactive research report for a ticker.

    Retrieves the latest research snapshot from BigQuery and renders
    a professional HTML report with KPI cards, financial charts,
    analyst findings, scenarios, evidence, and research history.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=422, detail="Ticker must be a non-empty string.")

    from investiq.reporting import build_report

    try:
        html = build_report(ticker)
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"No research snapshot found for ticker '{ticker}'. "
                   f"Use POST /research to generate one.",
        )
    except Exception:
        logger.exception("Failed to generate report for ticker %s", ticker)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report for ticker '{ticker}'. "
                   f"Check server logs for details.",
        )

    return HTMLResponse(content=html)


@app.get("/")
def index() -> RedirectResponse:
    """Default landing route — redirect to the InvestIQ dashboard."""
    return RedirectResponse(url="/investiq/HDFCBANK", status_code=302)


@app.get("/investiq")
def investiq_default() -> JSONResponse:
    """Default investiq route without ticker — return API info."""
    return JSONResponse(content={
        "detail": "Please specify a ticker. Usage: /investiq/{ticker}",
        "example": "/investiq/HDFCBANK",
    })


@app.get("/report")
def report_default() -> JSONResponse:
    """Default report route without ticker — return API info."""
    return JSONResponse(content={
        "detail": "Please specify a ticker. Usage: /report/{ticker}",
        "example": "/report/HDFCBANK",
    })


@app.get("/investiq/{ticker}")
def investiq_dashboard(ticker: str) -> HTMLResponse:
    """Serve the InvestIQ decision dashboard for a ticker."""
    from pathlib import Path
    from jinja2 import Environment, FileSystemLoader

    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=422, detail="Ticker must be a non-empty string.")

    tpl_dir = Path(__file__).resolve().parent.parent / "reporting" / "templates"
    env = Environment(loader=FileSystemLoader(str(tpl_dir)), autoescape=False)
    template = env.get_template("dashboard.html")

    html = template.render(ticker=ticker)
    return HTMLResponse(content=html)


@app.get("/api/v1/research/{ticker}")
def research_api(ticker: str) -> dict[str, Any]:
    """JSON API returning structured research data for a ticker."""
    from investiq.reporting import ReportDataFetcher
    from investiq.reporting.report import (
        _compute_upside,
        _format_generated_at,
        _build_thesis_groups,
        _build_analyst_intelligence,
        _build_scenario_cards,
        _build_evidence_summary,
        _build_history_timeline,
    )

    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=422, detail="Ticker must be a non-empty string.")

    try:
        fetcher = ReportDataFetcher()
        data = fetcher.fetch(ticker)
    except (LookupError, FileNotFoundError):
        raise HTTPException(
            status_code=404,
            detail=f"Research not available for ticker '{ticker}'.",
        )

    upside = _compute_upside(data.current_price, data.blended_fair_value)
    history_entries = _build_history_timeline(data.history)
    thesis_groups = _build_thesis_groups(data.thesis_items)
    analyst_findings = _build_analyst_intelligence(data.findings)
    evidence_groups = _build_evidence_summary(data.evidence)
    scenario_cards = _build_scenario_cards(data.scenarios)

    # Build evidence items for main display (non-model, clean labels)
    evidence_main = []
    for grp in evidence_groups:
        for item in grp.get("list", []):
            evidence_main.append({
                "domain": grp["domain"],
                "label": item.get("clean_label") or item.get("label", ""),
                "value": item.get("value"),
                "source": item.get("source"),
            })

    return {
        "snapshot_id": data.snapshot_id,
        "ticker": data.ticker,
        "company_name": data.company_name or data.ticker,
        "sector": data.sector,
        "company_type": data.company_type,
        "generated_at": _format_generated_at(data.generated_at),
        "current_price": data.current_price,
        "blended_fair_value": data.blended_fair_value,
        "upside_pct": upside,
        "valuation_verdict": data.valuation_verdict,
        "overall_assessment": data.overall_assessment,
        "executive_summary": data.executive_summary,
        "investment_thesis": data.investment_thesis,
        "num_findings": data.num_findings,
        "num_metrics_years": data.num_metrics_years,
        "thesis_groups": thesis_groups,
        "analyst_findings": analyst_findings,
        "scenario_cards": scenario_cards,
        "evidence_main": evidence_main,
        "history_entries": history_entries,
    }