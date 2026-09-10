"""BigQuery data retrieval for the reporting layer.

Reuses the existing BigQueryResearchRepository to access its client and
BigQuery connection.  No separate BigQuery credentials are needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd
from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
from investiq.storage.bigquery import BigQueryResearchRepository


logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


@dataclass
class ReportData:
    """All data needed to render a single-company investment report."""

    # Research snapshot (header)
    snapshot_id: str
    ticker: str
    company_name: str | None
    sector: str | None
    company_type: str | None
    generated_at: Any  # timestamp
    current_price: float | None
    blended_fair_value: float | None
    valuation_verdict: str | None
    overall_assessment: str | None
    executive_summary: str | None
    investment_thesis: str | None
    num_findings: int | None
    num_metrics_years: int | None

    # Child tables
    thesis_items: pd.DataFrame  # columns: snapshot_id, ticker, item_type, item_text
    metrics: pd.DataFrame       # columns: snapshot_id, ticker, fiscal_year, roe, roa, nim,
    findings: pd.DataFrame      # columns: snapshot_id, ticker, analyst, category, title,
    evidence: pd.DataFrame      # columns: snapshot_id, ticker, evidence_id, domain,
    scenarios: pd.DataFrame     # columns: snapshot_id, ticker, scenario, description
    history: pd.DataFrame       # past snapshots for the same ticker

    def has_history(self) -> bool:
        return not self.history.empty
def has_history(self) -> bool:
        return not self.history.empty


class ReportDataFetcher:
    """Fetches report data from BigQuery using the existing repository client."""

    def __init__(self, repository: BigQueryResearchRepository | None = None) -> None:
        if repository is None:
            repository = BigQueryResearchRepository()
        self._repo = repository
        self._client = repository.client
        self._dataset = repository.dataset_id
        self._project = self._client.project

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, ticker: str) -> ReportData:
        """Fetch all report data for the latest snapshot of *ticker*.

        Raises LookupError if no snapshot exists for the ticker.
        """
        ticker = ticker.strip().upper()
        snap_row = self._latest_snapshot(ticker)
        if snap_row is None:
            raise LookupError(f"No research snapshot found for ticker '{ticker}'.")

        sid = snap_row["snapshot_id"]

        return ReportData(
            snapshot_id=sid,
            ticker=ticker,
            company_name=snap_row.get("company_name"),
            sector=snap_row.get("sector"),
            company_type=snap_row.get("company_type"),
            generated_at=snap_row.get("generated_at"),
            current_price=_safe_float(snap_row.get("current_price")),
            blended_fair_value=_safe_float(snap_row.get("blended_fair_value")),
            valuation_verdict=snap_row.get("valuation_verdict"),
            overall_assessment=snap_row.get("overall_assessment"),
            executive_summary=snap_row.get("executive_summary"),
            investment_thesis=snap_row.get("investment_thesis"),
            num_findings=_safe_int(snap_row.get("num_findings")),
            num_metrics_years=_safe_int(snap_row.get("num_metrics_years")),
            thesis_items=self._table(sid, self._repo.TABLE_THESIS_ITEMS),
            metrics=self._table(sid, self._repo.TABLE_METRICS),
            findings=self._table(sid, self._repo.TABLE_FINDINGS),
            evidence=self._table(sid, self._repo.TABLE_EVIDENCE),
            scenarios=self._table(sid, self._repo.TABLE_SCENARIOS),
            history=self._all_snapshots(ticker, exclude_sid=sid),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _qualified(self, table: str) -> str:
        return f"`{self._project}.{self._dataset}.{table}`"

    def _latest_snapshot(self, ticker: str) -> dict[str, Any] | None:
        sql = (
            f"SELECT * FROM {self._qualified(self._repo.TABLE_SNAPSHOTS)} "
            f"WHERE ticker = @ticker "
            f"ORDER BY generated_at DESC "
            f"LIMIT 1"
        )
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("ticker", "STRING", ticker)]
        )
        rows = list(self._client.query(sql, job_config=job_config).result())
        if not rows:
            return None
        return dict(rows[0])

    def _table(self, snapshot_id: str, table_name: str) -> pd.DataFrame:
        sql = (
            f"SELECT * FROM {self._qualified(table_name)} "
            f"WHERE snapshot_id = @sid "
            f"ORDER BY snapshot_id"
        )
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("sid", "STRING", snapshot_id)]
        )
        rows = list(self._client.query(sql, job_config=job_config).result())
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])

    def _all_snapshots(self, ticker: str, exclude_sid: str | None = None) -> pd.DataFrame:
        sql = (
            f"SELECT * FROM {self._qualified(self._repo.TABLE_SNAPSHOTS)} "
            f"WHERE ticker = @ticker "
            f"ORDER BY generated_at DESC"
        )
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("ticker", "STRING", ticker)]
        )
        rows = list(self._client.query(sql, job_config=job_config).result())
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        if exclude_sid is not None and not df.empty:
            df = df[df["snapshot_id"] != exclude_sid]
        return df


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None