# InvestIQ — Google Cloud Run Dockerfile
#
# Production deployment configuration for the existing FastAPI research API.
# Uses Application Default Credentials (ADC) for BigQuery authentication.
# No credentials files are copied into the container.

FROM python:3.11-slim

WORKDIR /app

# Copy dependency manifest first (better Docker caching)
COPY pyproject.toml README.md ./

# Copy application source and required research data
COPY src/ ./src/
COPY data/ ./data/

# Install runtime dependencies in editable mode.
# Editable mode preserves source file paths so that the existing
# parents[3] data directory resolution continues to work correctly.
# Dev dependencies (pytest, etc.) are NOT installed in production.
RUN pip install --no-cache-dir -e "."

# Cloud Run provides the PORT environment variable at runtime.
# The application reads PORT (default 8080) from os.environ in __main__.py.
EXPOSE 8080

# Start the FastAPI server using the existing uvicorn entrypoint.
# Host 0.0.0.0 is required by Cloud Run's container runtime contract.
# Port is read from the PORT environment variable (set by Cloud Run).
# The .env file is excluded from the build context via .dockerignore.
# BigQuery authentication uses Cloud Run service identity (ADC).
CMD ["python", "-m", "investiq"]