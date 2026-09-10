"""Google BigQuery persistence for ResearchSnapshot data.

Stores research results in Looker-friendly relational tables.
Cloud Run service identity is used for authentication.
"""

from __future__ import annotations
import logging
from typing import Any
from investiq.models.research import ResearchSnapshot

logger = logging.getLogger(__name__)


class BigQueryResearchRepository:
    """Persists ResearchSnapshot data to BigQuery tables.

    Uses Application Default Credentials (ADC) for authentication.
    Credentials are never hardcoded in source code — use GOOGLE_APPLICATION_CREDENTIALS
    environment variable or Cloud Run service identity.

    Configuration is driven by environment variables:
        GCP_PROJECT_ID       — Google Cloud project ID (optional, falls back to ADC default)
        BIGQUERY_DATASET      — Dataset name (default: investiq)
        BIGQUERY_LOCATION     — Dataset location (default: asia-south1)
    """

    TABLE_SNAPSHOTS = "research_snapshots"
    TABLE_METRICS = "research_metrics"
    TABLE_FINDINGS = "research_findings"
    TABLE_EVIDENCE = "research_evidence"
    TABLE_SCENARIOS = "research_scenarios"
    TABLE_THESIS_ITEMS = "research_thesis_items"

    # DDL statements from infra/bigquery/schema.sql — source of truth
    _CREATE_TABLE_DDL: dict[str, str] = {
        TABLE_SNAPSHOTS: (
            "CREATE TABLE IF NOT EXISTS {dataset}.`{table}` ("
            "    snapshot_id          STRING NOT NULL,"
            "    ticker               STRING NOT NULL,"
            "    company_name         STRING,"
            "    sector               STRING,"
            "    company_type         STRING,"
            "    generated_at         TIMESTAMP,"
            "    current_price        FLOAT64,"
            "    blended_fair_value   FLOAT64,"
            "    valuation_verdict    STRING,"
            "    overall_assessment   STRING,"
            "    executive_summary    STRING,"
            "    investment_thesis    STRING,"
            "    num_findings         INT64,"
            "    num_metrics_years    INT64,"
            "    PRIMARY KEY (snapshot_id) NOT ENFORCED"
            ")"
        ),
        TABLE_METRICS: (
            "CREATE TABLE IF NOT EXISTS {dataset}.`{table}` ("
            "    snapshot_id       STRING NOT NULL,"
            "    ticker            STRING NOT NULL,"
            "    fiscal_year       STRING NOT NULL,"
            "    roe               FLOAT64,"
            "    roa               FLOAT64,"
            "    nim               FLOAT64,"
            "    casa_ratio        FLOAT64,"
            "    cost_to_income    FLOAT64,"
            "    eps               FLOAT64,"
            "    bvps              FLOAT64,"
            "    gross_npa_ratio   FLOAT64,"
            "    net_npa_ratio     FLOAT64,"
            "    credit_cost       FLOAT64"
            ")"
        ),
        TABLE_FINDINGS: (
            "CREATE TABLE IF NOT EXISTS {dataset}.`{table}` ("
            "    snapshot_id               STRING NOT NULL,"
            "    ticker                    STRING NOT NULL,"
            "    analyst                   STRING,"
            "    category                  STRING,"
            "    title                     STRING,"
            "    statement                 STRING,"
            "    confidence                FLOAT64,"
            "    fundamental_observation   STRING,"
            "    why_it_matters            STRING,"
            "    positive_implication      STRING,"
            "    negative_implication      STRING,"
            "    thesis_breaker            STRING,"
            "    evidence_ids              ARRAY<STRING>"
            ")"
        ),
        TABLE_EVIDENCE: (
            "CREATE TABLE IF NOT EXISTS {dataset}.`{table}` ("
            "    snapshot_id        STRING NOT NULL,"
            "    ticker             STRING NOT NULL,"
            "    evidence_id        STRING NOT NULL,"
            "    domain             STRING,"
            "    tag                STRING,"
            "    source             STRING,"
            "    source_field       STRING,"
            "    source_url         STRING,"
            "    publication_date   DATE,"
            "    label              STRING,"
            "    value              STRING"
            ")"
        ),
        TABLE_SCENARIOS: (
            "CREATE TABLE IF NOT EXISTS {dataset}.`{table}` ("
            "    snapshot_id   STRING NOT NULL,"
            "    ticker        STRING NOT NULL,"
            "    scenario      STRING NOT NULL,"
            "    description   STRING"
            ")"
        ),
        TABLE_THESIS_ITEMS: (
            "CREATE TABLE IF NOT EXISTS {dataset}.`{table}` ("
            "    snapshot_id   STRING NOT NULL,"
            "    ticker        STRING NOT NULL,"
            "    item_type     STRING,"
            "    item_text     STRING"
            ")"
        ),
    }

    def __init__(self, project_id=None, dataset_id=None, location="asia-south1"):
        import os
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self.dataset_id = dataset_id or os.environ.get("BIGQUERY_DATASET", "investiq")
        self.location = os.environ.get("BIGQUERY_LOCATION", location)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google.cloud import bigquery
            if self.project_id:
                self._client = bigquery.Client(project=self.project_id, location=self.location)
            else:
                self._client = bigquery.Client(location=self.location)
        return self._client

    def initialize_dataset(self) -> None:
        """Ensure the configured dataset and all 6 tables exist.

        Creates the dataset with the configured location if it does not exist.
        Creates all six required tables using the DDL defined in this class.

        This method is idempotent — safe to call multiple times.
        Raises on authentication or permission errors.
        """
        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound

        client = self.client
        dataset_ref = bigquery.DatasetReference(
            client.project, self.dataset_id
        )

        # Create dataset if it does not exist
        try:
            client.get_dataset(dataset_ref)
            logger.debug("Dataset %s already exists", self.dataset_id)
        except NotFound:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = self.location
            client.create_dataset(dataset, timeout=30)
            logger.info("Created dataset %s in %s", self.dataset_id, self.location)

        # Create each table if it does not exist
        for table_name, ddl in self._CREATE_TABLE_DDL.items():
            create_stmt = ddl.format(
                dataset=f"`{client.project}`.`{self.dataset_id}`",
                table=table_name,
            )
            logger.debug(
                "Creating table %s in dataset %s (project=%s, location=%s)",
                table_name, self.dataset_id, client.project, self.location,
            )
            try:
                client.query(create_stmt).result()
                logger.debug("Table %s.%s ready", self.dataset_id, table_name)
            except Exception as exc:
                logger.error("Failed to create table %s.%s: %s", self.dataset_id, table_name, exc)
                raise

        logger.info(
            "BigQuery dataset %s (%s) initialized with all 6 tables",
            self.dataset_id,
            client.project,
        )

    def save_snapshot(self, snapshot):
        ticker = snapshot.ticker
        sid = snapshot.snapshot_id
        logger.info("Saving snapshot %s for %s to BigQuery", sid, ticker)
        snap_row = self._build_snapshot_row(snapshot)
        metric_rows = self._build_metric_rows(snapshot)
        finding_rows = self._build_finding_rows(snapshot)
        evidence_rows = self._build_evidence_rows(snapshot)
        scenario_rows = self._build_scenario_rows(snapshot)
        thesis_rows = self._build_thesis_rows(snapshot)
        errors = []
        for table_name, rows in [
            (self.TABLE_SNAPSHOTS, [snap_row] if snap_row else []),
            (self.TABLE_METRICS, metric_rows),
            (self.TABLE_FINDINGS, finding_rows),
            (self.TABLE_EVIDENCE, evidence_rows),
            (self.TABLE_SCENARIOS, scenario_rows),
            (self.TABLE_THESIS_ITEMS, thesis_rows),
        ]:
            if not rows: continue
            try:
                self._merge_rows(table_name, rows, sid)
            except Exception as exc:
                logger.error("Failed to write %d rows to %s: %s", len(rows), table_name, exc)
                errors.append(str(exc))
        if errors:
            raise RuntimeError("BigQuery persistence errors: " + "; ".join(errors))
    def _build_snapshot_row(self, snap):
        company = snap.company
        val = snap.valuation
        cio = snap.cio_synthesis
        return {
            "snapshot_id": snap.snapshot_id,
            "ticker": snap.ticker,
            "company_name": company.name,
            "sector": company.sector.value if company.sector else None,
            "company_type": company.company_type.value if company.company_type else None,
            "generated_at": snap.generated_at.isoformat(),
            "current_price": val.methods[0].current_price if val.methods else None,
            "blended_fair_value": val.blended_fair_value,
            "valuation_verdict": val.verdict,
            "overall_assessment": cio.overall_assessment if cio else None,
            "executive_summary": cio.executive_summary if cio else None,
            "investment_thesis": cio.investment_thesis if cio else None,
            "num_findings": len(snap.findings),
            "num_metrics_years": len(snap.metrics),
        }
    def _build_metric_rows(self, snap):
        rows = []
        for m in snap.metrics:
            rows.append({
                "snapshot_id": snap.snapshot_id, "ticker": snap.ticker,
                "fiscal_year": m.fiscal_year, "roe": m.roe, "roa": m.roa,
                "nim": m.nim, "casa_ratio": m.casa_ratio,
                "cost_to_income": m.cost_to_income, "eps": m.eps,
                "bvps": m.book_value_per_share,
                "gross_npa_ratio": m.gross_npa_ratio,
                "net_npa_ratio": m.net_npa_ratio, "credit_cost": m.credit_cost,
            })
        return rows
    def _build_finding_rows(self, snap):
        rows = []
        for f in snap.findings:
            rows.append({
                "snapshot_id": snap.snapshot_id, "ticker": snap.ticker,
                "analyst": f.analyst,
                "category": f.category.value if f.category else None,
                "title": f.title, "statement": f.statement,
                "confidence": f.confidence,
                "fundamental_observation": f.fundamental_observation,
                "why_it_matters": f.why_it_matters,
                "positive_implication": f.positive_implication,
                "negative_implication": f.negative_implication,
                "thesis_breaker": f.thesis_breaker,
                "evidence_ids": f.evidence_ids,
            })
        return rows
    def _build_evidence_rows(self, snap):
        rows = []
        for ev in snap.evidence_chain:
            rows.append({
                "snapshot_id": snap.snapshot_id, "ticker": snap.ticker,
                "evidence_id": ev.evidence_id,
                "domain": ev.domain.value if ev.domain else None,
                "tag": ev.tag.value if ev.tag else None,
                "source": ev.source, "source_field": ev.source_field,
                "source_url": ev.source_url,
                "publication_date": ev.publication_date.isoformat() if ev.publication_date else None,
                "label": ev.label, "value": ev.value,
            })
        return rows
    def _build_scenario_rows(self, snap):
        cio = snap.cio_synthesis
        if not cio: return []
        return [
            {"snapshot_id": snap.snapshot_id, "ticker": snap.ticker, "scenario": "BULL", "description": cio.bull_case},
            {"snapshot_id": snap.snapshot_id, "ticker": snap.ticker, "scenario": "BASE", "description": cio.base_case},
            {"snapshot_id": snap.snapshot_id, "ticker": snap.ticker, "scenario": "BEAR", "description": cio.bear_case},
        ]
    def _build_thesis_rows(self, snap):
        cio = snap.cio_synthesis
        if not cio: return []
        rows = []
        for s in cio.key_strengths:
            rows.append({"snapshot_id": snap.snapshot_id, "ticker": snap.ticker, "item_type": "STRENGTH", "item_text": s})
        for c in cio.key_concerns:
            rows.append({"snapshot_id": snap.snapshot_id, "ticker": snap.ticker, "item_type": "CONCERN", "item_text": c})
        for g in cio.growth_drivers:
            rows.append({"snapshot_id": snap.snapshot_id, "ticker": snap.ticker, "item_type": "GROWTH_DRIVER", "item_text": g})
        for r in cio.risks:
            rows.append({"snapshot_id": snap.snapshot_id, "ticker": snap.ticker, "item_type": "RISK", "item_text": r})
        for t in cio.thesis_breakers:
            rows.append({"snapshot_id": snap.snapshot_id, "ticker": snap.ticker, "item_type": "THESIS_BREAKER", "item_text": t})
        return rows
    def _fully_qualified_table(self, table_name):
        """Return fully-qualified table reference using the client's resolved project."""
        return f"{self.client.project}.{self.dataset_id}.{table_name}"

    def _merge_rows(self, table_name, rows, snapshot_id):
        from google.cloud import bigquery
        from google.cloud.bigquery import ScalarQueryParameter, LoadJobConfig
        table_ref = self._fully_qualified_table(table_name)
        delete_sql = f"DELETE FROM `{table_ref}` WHERE snapshot_id = @snapshot_id"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)]
        )
        self.client.query(delete_sql, job_config=job_config).result()
        if rows:
            # Use a load job instead of insert_rows_json to avoid the
            # BigQuery streaming buffer limitation. Data written via a load
            # job is immediately available for subsequent DML operations.
            load_config = LoadJobConfig()
            load_job = self.client.load_table_from_json(rows, table_ref, job_config=load_config)
            load_job.result()
            if load_job.errors:
                raise RuntimeError(f"load_table_from_json errors: {load_job.errors}")
        logger.debug("Wrote %d rows to %s (snapshot=%s)", len(rows), table_name, snapshot_id)
