# InvestIQ

AI-powered institutional-style equity research platform for individual investors, focused on Indian listed companies.

## Status

**Milestone 1** — Foundational calculation engine and data models.

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start API server (Phase 2)
# uvicorn investiq.api.app:app --reload
```

## Architecture

See the implementation plan for the full architecture proposal.

## First Golden Test

```bash
# Run HDFC Bank metric and valuation tests
pytest tests/ -v -k "hdfcbank or HDFCBANK"
```

---

## Google Cloud Run Deployment

### Prerequisites

1. **Google Cloud project** with billing enabled.
2. **Google Cloud CLI** installed and authenticated.

   ```bash
   gcloud auth login
   gcloud config set project PROJECT_ID
   ```

3. **Required APIs** enabled:

   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   ```

### Deployment

From the project root directory, run:

```bash
gcloud run deploy investiq-api \
  --source . \
  --region asia-south1
```

Cloud Run will:
1. Build the application container using the provided `Dockerfile`.
2. Push the container to Cloud Build/Artifact Registry.
3. Deploy the service to Cloud Run in `asia-south1`.

**Important:** For the hackathon demo, the API may need to be publicly reachable by the frontend. When Cloud Run asks:

> Allow unauthenticated invocations?

Select **yes** (public access) if the API needs to be reachable without authentication.  
Select **no** (private access) if all requests will come from authenticated sources.

> **Security note:** The current deployment uses `MockLLMProvider` with deterministic responses. No API keys or secrets are required or exposed.

### Local Cloud-Run-Equivalent Test

Before deploying, verify the server works with the same runtime contract:

```bash
# Set PORT environment variable (Cloud Run provides this)
$env:PORT=8080

# Start the server
python -m investiq
```

Then test in another terminal:

```bash
# Health check
curl http://localhost:8080/health

# HDFC Bank research
## Interactive Research Report

### GET /report/{ticker}

Generate a professional, interactive investment research report for any ticker with a persisted BigQuery snapshot.

Examples:

```bash
# HDFC Bank research report
curl http://localhost:8000/report/HDFCBANK

# ICICI Bank research report  
curl http://localhost:8000/report/ICICIBANK
```

The report is **dynamically generated** from BigQuery-persisted data and includes:

| Section | Description |
|---------|-------------|
| Investment Overview | Company identity, overall assessment, executive summary, investment thesis |
| KPI Cards | Current price, fair value, upside/downside, valuation verdict, findings count, metric years |
| Thesis at a Glance | Key strengths, concerns, growth drivers, risks, thesis breakers |
| Financial Intelligence | Interactive Plotly charts: ROE/ROA, NIM, CASA ratio, cost-to-income, NPA, EPS/BVPS, credit cost |
| Analyst Intelligence | Findings grouped by analyst with confidence indicators |
| Scenario Analysis | Bull/base/bear scenarios |
| Evidence Trail | Structured evidence table with source links |
| Research History | Previous research runs for the same ticker |

**Features:**
- Ticker-agnostic — works for **any** ticker with a persisted snapshot (not limited to HDFC/ICICI)
- Ticker normalization: `strip()` + `upper()`
- Latest snapshot automatically selected via `ORDER BY generated_at DESC LIMIT 1`
- All child records filtered by `snapshot_id`
- Interactive Plotly charts (hover, zoom, pan)
- Professional CSS — responsive, print-friendly
- Missing data handled gracefully (N/A, unavailable messages)
- No hardcoded company names, values, or ticker-specific logic

**Error responses:**
```
GET /report/UNKNOWN_TICKER → 404 Not Found
GET /report/              → 422 Validation Error
```

The report uses:
- **BigQuery** — source of truth
- **Pandas** — data transformation
- **Plotly** — interactive charts
- **Jinja2** — HTML templating
- **FastAPI** — HTTP endpoint

No frontend framework. No authentication. No live market data.

> **Note:** The report works for any ticker where `POST /research` has been run and persisted to BigQuery. It does **not** mean every Indian listed company is currently supported by the research engine.
curl -X POST http://localhost:8080/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"HDFCBANK"}'

# ICICI Bank research
curl -X POST http://localhost:8080/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"ICICIBANK"}'

# Unknown ticker (should return 404)
curl -X POST http://localhost:8080/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"UNKNOWN_TICKER"}'
```

### Post-Deployment Verification

After deployment, capture the Cloud Run service URL (shown at the end of `gcloud run deploy`), then test:

```bash
# Health check
curl https://<cloud-run-url>/health

# HDFC Bank research
curl -X POST https://<cloud-run-url>/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"HDFCBANK"}'

# ICICI Bank research
curl -X POST https://<cloud-run-url>/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"ICICIBANK"}'

# Unknown ticker (should return 404)
curl -X POST https://<cloud-run-url>/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"UNKNOWN_TICKER"}'
```

### Architecture

```
Internet
   ↓
Cloud Run
   ↓
FastAPI
   ↓
ResearchOrchestrator
   ↓
Deterministic Calculators
   ↓
Evidence Collection
   ↓
3 Analysts
   ↓
CIO Synthesis
   ↓
ResearchSnapshot
```

### Environment Configuration (Current Phase)

- **LLM Provider:** `MockLLMProvider` (deterministic, zero-cost, zero external API calls) — default development mode
- **No Gemini/LLM API keys required** for local development
- **No secrets required** in Cloud Run if using mock mode
- **No authentication** (public access for hackathon demo)

### Gemini Configuration (Production)

The application supports switching from `MockLLMProvider` to `GeminiLLMProvider` at runtime through environment configuration.

#### Provider Selection

Set the following environment variables to enable Gemini:

```bash
# Select the production LLM provider
LLM_PROVIDER=gemini

# Specify the Gemini model (optional, default: gemini-3.5-flash-lite)
GEMINI_MODEL=gemini-3.5-flash-lite

# Google Gemini API key
GEMINI_API_KEY=your_api_key_here

# Explicitly authorize external LLM API calls
INVESTIQ_ALLOW_REAL_LLM=true
```

#### Provider Modes

| Mode | `LLM_PROVIDER` | Description |
|------|---------------|-------------|
| Mock (default) | `mock` | Deterministic, zero-cost, no external API calls. Used for testing and local development. |
| Gemini | `gemini` | Production Gemini LLM via `google-genai` SDK. Requires valid `GEMINI_API_KEY` and `INVESTIQ_ALLOW_REAL_LLM=true`. |

#### Architecture

```
LLMProvider (abstract)
       │
       ├── MockLLMProvider (testing/local)
       │     • Deterministic synthetic responses
       │     • Zero external API calls
       │     • Zero cost
       │     • Does not require credentials
       │
       └── GeminiLLMProvider (production)
             • Uses google.genai SDK (v2.0.1+)
             • Structured JSON output with Pydantic validation
             • Token and cost tracking
             • Secret masking in error messages
             • Google Cloud API key authentication
```

#### Security Notes

- **Never commit API keys** to source control. Use environment variables or Google Cloud Secret Manager.
- The `.env` file is `.gitignore`d and should never be committed.
- In Cloud Run, set `GEMINI_API_KEY` as an environment variable or use Secret Manager.
- `GeminiLLMProvider` automatically masks the API key from error messages and logs.

### Cloud Run Production Configuration

When deploying with Gemini to Cloud Run, set these environment variables:

```bash
gcloud run deploy investiq-api \
  --source . \
  --region asia-south1 \
  --set-env-vars="LLM_PROVIDER=gemini,GEMINI_MODEL=gemini-3.5-flash-lite,INVESTIQ_ALLOW_REAL_LLM=true" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest"
```

> **Note:** The example above uses Secret Manager for the API key (`--set-secrets`). To use a plain environment variable instead of secrets, add `GEMINI_API_KEY=your_key` to `--set-env-vars`. Prefer Secret Manager for production deployments.

### Local Integration Test (Gemini)

To verify the Gemini provider locally (requires valid credentials):

```bash
set LLM_PROVIDER=gemini
set GEMINI_API_KEY=your_key
set GEMINI_MODEL=gemini-3.5-flash-lite
set INVESTIQ_ALLOW_REAL_LLM=true

python -m investiq
```

Then test with:

```bash
curl -X POST http://localhost:8080/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"HDFCBANK"}'
```

> **Important:** This makes real API calls and incurs token costs. Never run this in CI/CD pipelines.

### Runtime Configuration

| Setting | Value |
|---------|-------|
| Service name | `investiq-api` |
| Region | `asia-south1` (Mumbai, India) |
| Port | `8080` (Cloud Run injects via `PORT` env var) |
| Host | `0.0.0.0` (Cloud Run container runtime contract) |
| Python | 3.11+ |
| Data directory | `data/prepared/` (included in container) |
---

## Production Gemini Research — Deployment & Verification

### Architecture (Production)

```
User
 ↓
HTTPS /research
 ↓
Cloud Run (asia-south1)
 ↓
FastAPI
 ↓
ResearchOrchestrator
 ↓
Deterministic Calculations (Metrics, Valuation, Evidence)
 ↓
3 Specialized Analysts (via LLMProvider abstraction)
 ↓
CIO Synthesis (via LLMProvider abstraction)
 ↓
ResearchSnapshot
 ↓
JSON Response
```

All LLM operations use the same `GeminiProvider` injected at the application boundary in `app.py`. Analysts and CIO are completely provider-agnostic.

### 1. Create the Gemini API Secret in Google Cloud Secret Manager

```bash
# Create the secret
gcloud secrets create gemini-api-key \
  --replication-policy="automatic"

# Add the secret value (paste your Gemini API key when prompted)
echo -n "AIzaSy..." | gcloud secrets versions add gemini-api-key --data-file=-
```

> **⚠️ Security:** Never type the API key directly into a command that will appear in shell history. Use a file redirected from a secure source, or the GCP Console UI.

### 2. Grant Cloud Run access to the secret

```bash
# Get the project number
PROJECT_NUMBER=$(gcloud projects describe PROJECT_ID --format="value(projectNumber)")

# Grant the Cloud Run service agent access to read the secret
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 3. Deploy with Gemini configuration

```bash
gcloud run deploy investiq-api \
  --source . \
  --region asia-south1 \
  --set-env-vars="LLM_PROVIDER=gemini,GEMINI_MODEL=gemini-3.5-flash-lite,INVESTIQ_ALLOW_REAL_LLM=true" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest"
```

Cloud Run will:
1. Build the container using the existing `Dockerfile`.
2. Inject the secret as the `GEMINI_API_KEY` environment variable.
3. Start the FastAPI server with `GeminiProvider`.

> **Note:** Replace `GEMINI_MODEL=gemini-3.5-flash-lite` with the actual model you wish to use (e.g., `gemini-1.5-pro`, `gemini-2.0-flash`).

### 4. Verify the deployment

**Health check:**
```bash
curl https://<cloud-run-url>/health
# Expected: {"status": "ok"}
```

**HDFC Bank research:**
```bash
curl -X POST https://<cloud-run-url>/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"HDFCBANK"}'
```

Verify the response contains:
- `ticker`: `"HDFCBANK"`
- `company.name`: `"HDFC Bank Limited"`
- `metrics`: Array of 5 fiscal years (FY2021–FY2025) with calculated banking metrics
- `valuation`: Blended fair value and verdict (Undervalued / Overvalued / Fairly Valued)
- `findings`: Array containing findings from all 3 analysts (`financial_analyst`, `asset_quality_analyst`, `banking_business_analyst`)
- `evidence_chain`: Array of `EvidenceItem` objects
- `cio_synthesis`: Structured CIO investment thesis with executive summary, bull/base/bear cases
- `snapshot_id`: UUID

**ICICI Bank research (cross-company verification):**
```bash
curl -X POST https://<cloud-run-url>/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"ICICIBANK"}'
```

Verify:
- `ticker`: `"ICICIBANK"`
- `company.name`: `"ICICI Bank Limited"`
- No HDFC contamination in company, metrics, or valuation data

**Unknown ticker:**
```bash
curl -X POST https://<cloud-run-url>/research \
  -H "Content-Type: application/json" \
  -d '{"ticker":"UNKNOWN_TICKER"}'
# Expected: HTTP 404
```

### 5. Switch back to mock mode

To revert to deterministic mock mode (e.g., for testing or cost control):

```bash
gcloud run deploy investiq-api \
  --source . \
  --region asia-south1 \
  --clear-env-vars \
  --clear-secrets
```

The default `LLM_PROVIDER=mock` (hardcoded in `config.py`) will take effect, and no API key is required.

### Environment Summary

| Variable | Development (Mock) | Production (Gemini) |
|----------|-------------------|-------------------|
| `LLM_PROVIDER` | `mock` (default) | `gemini` |
| `INVESTIQ_ALLOW_REAL_LLM` | `false` (default) | `true` |
| `GEMINI_API_KEY` | Not required | Required (Secret Manager) |
| `GEMINI_MODEL` | Not used | `gemini-3.5-flash-lite` (or as configured) |
| `MAX_EXTERNAL_LLM_CALLS` | `0` (default) | `0` (unlimited) |
---

## BigQuery Research Persistence

### Architecture

```
Firebase / API Client
        ↓
Cloud Run
        ↓
FastAPI
        ↓
ResearchOrchestrator
        ↓
ResearchSnapshot
        ↓
BigQueryResearchRepository
        ↓
BigQuery (6 tables)
        ↓
Looker (next phase)
```

### Required APIs

```bash
gcloud services enable bigquery.googleapis.com
```

### Dataset Creation

```bash
# Create the BigQuery dataset
bq --location=asia-south1 mk \
  --dataset --description="InvestIQ research data" \
  PROJECT_ID:investiq
```

### Table Creation

The required tables are defined in `infra/bigquery/schema.sql`. There are 6 tables:

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `research_snapshots` | One row per research run | `snapshot_id`, `ticker`, `company_name`, `generated_at`, `blended_fair_value`, `valuation_verdict`, `executive_summary` |
| `research_metrics` | One row per fiscal year per snapshot | `snapshot_id`, `ticker`, `fiscal_year`, `roe`, `roa`, `nim`, `casa_ratio`, `gross_npa_ratio`, `net_npa_ratio` |
| `research_findings` | One row per analyst finding | `snapshot_id`, `ticker`, `analyst`, `category`, `title`, `statement`, `confidence`, `evidence_ids` |
| `research_evidence` | One row per evidence item | `snapshot_id`, `ticker`, `evidence_id`, `domain`, `tag`, `source`, `value` |
| `research_scenarios` | Bull/base/bear CIO scenarios | `snapshot_id`, `ticker`, `scenario`, `description` |
| `research_thesis_items` | Strengths, concerns, risks, growth drivers | `snapshot_id`, `ticker`, `item_type`, `item_text` |

Run the schema:

```bash
bq query --location=asia-south1 --project_id=PROJECT_ID \
  "$(cat infra/bigquery/schema.sql)"
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GCP_PROJECT_ID` | `""` (ADC) | Google Cloud project ID for BigQuery |
| `BIGQUERY_DATASET` | `investiq` | BigQuery dataset name |
| `BIGQUERY_LOCATION` | `asia-south1` | BigQuery dataset location |

### Cloud Run Service Account Permissions

The Cloud Run runtime service account needs the following role on the BigQuery dataset:

```bash
# Grant the Cloud Run service account BigQuery Data Editor role
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# Or for the default compute service account
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:$(gcloud projects describe PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
```

No service account JSON keys are used — the Cloud Run runtime identity (ADC) handles authentication automatically.

### Local Development Behavior

When running locally without Google Cloud credentials, the application automatically falls back to `FakeBigQueryResearchRepository` — an in-memory fake that stores snapshots without requiring BigQuery. This means:

- **No BigQuery credentials required** for local development
- **No network access required** for tests
- **All tests pass** without BigQuery
- **Research results are returned normally** even if persistence fails

### Data Flow

```
POST /research
      ↓
ResearchSnapshot generated
      ↓
save_snapshot() called
      ↓
snapshot_id scoped writes:
  1. research_snapshots (1 row)
  2. research_metrics (N rows, one per fiscal year)
  3. research_findings (N rows, one per finding)
  4. research_evidence (N rows, one per evidence item)
  5. research_scenarios (3 rows: BULL, BASE, BEAR)
  6. research_thesis_items (N rows)
      ↓
Idempotent: DELETE + INSERT per snapshot_id
      ↓
JSON response returned to client
```

### Persistence Failure Behavior

Research generation is more important than persistence. If the snapshot is generated successfully but BigQuery write fails:

- The error is logged
- The research result is still returned to the client (HTTP 200)
- The client is not blocked or given an error response

### Multi-Company Verification

Each research run is uniquely identified by `snapshot_id`. Two runs for the same ticker produce different `snapshot_id` values. All child tables are scoped by `snapshot_id` + `ticker`, ensuring:

- HDFCBANK data never contaminates ICICIBANK records
- Multiple research runs for the same company are independently stored
- Looker can filter by ticker, snapshot_id, or generated_at
