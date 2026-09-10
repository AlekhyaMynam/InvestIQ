"""InvestIQ HTTP API — production research endpoint.

Exposes the existing ResearchOrchestrator through a minimal HTTP API
for deployment to Cloud Run and consumption by web frontends.
Uses the project's existing Pydantic models directly.
"""

from investiq.api.app import app

__all__ = ["app"]