-- InvestIQ BigQuery Schema
-- Dataset: investiq (configurable via BIGQUERY_DATASET env var)
-- Location: asia-south1 (configurable via BIGQUERY_LOCATION env var)
--
-- Run: bq query --location=asia-south1 --project_id=PROJECT_ID < schema.sql

-- ────────────────────────────────────────────────────────────────────
-- Table 1: research_snapshots (one row per research run)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investiq.research_snapshots (
    snapshot_id          STRING NOT NULL,
    ticker               STRING NOT NULL,
    company_name         STRING,
    sector               STRING,
    company_type         STRING,
    generated_at         TIMESTAMP,
    current_price        FLOAT64,
    blended_fair_value   FLOAT64,
    valuation_verdict    STRING,
    overall_assessment   STRING,
    executive_summary    STRING,
    investment_thesis    STRING,
    num_findings         INT64,
    num_metrics_years    INT64,
    PRIMARY KEY (snapshot_id) NOT ENFORCED
);

-- ────────────────────────────────────────────────────────────────────
-- Table 2: research_metrics (one row per ticker / fiscal year)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investiq.research_metrics (
    snapshot_id       STRING NOT NULL,
    ticker            STRING NOT NULL,
    fiscal_year       STRING NOT NULL,
    roe               FLOAT64,
    roa               FLOAT64,
    nim               FLOAT64,
    casa_ratio        FLOAT64,
    cost_to_income    FLOAT64,
    eps               FLOAT64,
    bvps              FLOAT64,
    gross_npa_ratio   FLOAT64,
    net_npa_ratio     FLOAT64,
    credit_cost       FLOAT64
);

-- ────────────────────────────────────────────────────────────────────
-- Table 3: research_findings (one row per analyst finding)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investiq.research_findings (
    snapshot_id               STRING NOT NULL,
    ticker                    STRING NOT NULL,
    analyst                   STRING,
    category                  STRING,
    title                     STRING,
    statement                 STRING,
    confidence                FLOAT64,
    fundamental_observation   STRING,
    why_it_matters            STRING,
    positive_implication      STRING,
    negative_implication      STRING,
    thesis_breaker            STRING,
    evidence_ids              ARRAY<STRING>
);

-- ────────────────────────────────────────────────────────────────────
-- Table 4: research_evidence (one row per evidence item)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investiq.research_evidence (
    snapshot_id        STRING NOT NULL,
    ticker             STRING NOT NULL,
    evidence_id        STRING NOT NULL,
    domain             STRING,
    tag                STRING,
    source             STRING,
    source_field       STRING,
    source_url         STRING,
    publication_date   DATE,
    label              STRING,
    value              STRING
);

-- ────────────────────────────────────────────────────────────────────
-- Table 5: research_scenarios (bull/base/bear cases)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investiq.research_scenarios (
    snapshot_id   STRING NOT NULL,
    ticker        STRING NOT NULL,
    scenario      STRING NOT NULL,
    description   STRING
);

-- ────────────────────────────────────────────────────────────────────
-- Table 6: research_thesis_items (strengths, concerns, risks, etc.)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investiq.research_thesis_items (
    snapshot_id   STRING NOT NULL,
    ticker        STRING NOT NULL,
    item_type     STRING,
    item_text     STRING
);