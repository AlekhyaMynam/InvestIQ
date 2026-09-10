# InvestIQ — BigQuery Infrastructure

This directory contains the BigQuery schema and documentation for the
InvestIQ research persistence layer.

## Dataset

- **Dataset name:** `investiq` (configurable via `BIGQUERY_DATASET` env var)
- **Location:** `asia-south1` (configurable via `BIGQUERY_LOCATION` env var)

## Required Tables

1. `research_snapshots` — One row per completed research run
2. `research_metrics` — Per-fiscal-year bank metrics
3. `research_findings` — Analyst findings
4. `research_evidence` — Evidence items used in the research
5. `research_scenarios` — Bull/base/bear case
6. `research_thesis_items` — Strengths, concerns, risks, growth drivers

## Schema

The canonical schema is defined in `schema.sql`. The application also
embeds the same DDL in `src/investiq/storage/bigquery.py` as the
`_CREATE_TABLE_DDL` dictionary, which is used by the
`initialize_dataset()` method to create tables at runtime.

## Authentication

### Local Development

Use Application Default Credentials (ADC):

```bash
# Option 1: Set environment variable pointing to your service account key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Option 2: Authenticate via gcloud CLI (no JSON file needed)
gcloud auth application-default login
```

The application reads:
- `GCP_PROJECT_ID` from environment (optional; falls back to ADC default project)
- `GOOGLE_APPLICATION_CREDENTIALS` via Google client library

### Google Cloud Run (Production)

**DO NOT** copy service account JSON keys into the Docker image.

Instead, assign the Cloud Run service identity the required BigQuery
permissions:

1. Go to **Cloud Run → your-service → REVISION → Edit & Deploy New Revision**
2. Under **Container → Security**, set the **Service account** to one with BigQuery access
3. Deploy

The minimum BigQuery permission for writing snapshots is:

```text
roles/bigquery.dataEditor
```

This role includes:
- `bigquery.datasets.get`
- `bigquery.tables.create`
- `bigquery.tables.get`
- `bigquery.tables.updateData`
- `bigquery.tables.delete`

For fewer privileges, create a custom role with only the specific
permissions needed.

## Initialization

The `initialize_dataset()` method on `BigQueryResearchRepository`
creates the dataset and all six tables if they do not exist. It is
idempotent and safe to call on every startup.

```python
from investiq.storage import BigQueryResearchRepository

repo = BigQueryResearchRepository()
repo.initialize_dataset()  # Creates dataset + tables if missing
```

## Runtime Permissions

| Action | Required Permission |
|---|---|
| Create dataset | `bigquery.datasets.create` |
| Read dataset | `bigquery.datasets.get` |
| Create tables | `bigquery.tables.create` |
| Delete snapshot rows | `bigquery.tables.updateData` |
| Insert snapshot rows | `bigquery.tables.updateData` |
| Query tables | `bigquery.tables.getData` |

## Merge Strategy

The repository uses a **DELETE/INSERT** strategy for idempotency:

1. Delete all rows in each table where `snapshot_id = @snapshot_id`
2. Insert the new rows

This ensures saving the same snapshot twice does not create duplicates.
The merge is performed within each table independently. There is no
cross-table transaction — each table is deleted then inserted separately.