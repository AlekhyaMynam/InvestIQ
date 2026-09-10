"""Evidence model — the backbone of traceability in InvestIQ.

Every calculated metric, finding, or conclusion carries an evidence trail
that links it back to its source data, making research auditable and
drill-downable.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceTag(str, Enum):
    """Classification of evidence type.

    Distinguishes facts from calculations, assumptions, inferences,
    and synthesized opinions — a core InvestIQ design principle.
    """

    FACT = "FACT"                  # Directly from financial statements or filings
    CALCULATION = "CALCULATION"    # Deterministic computation from facts
    ASSUMPTION = "ASSUMPTION"     # Stated assumption (e.g., cost of equity)
    INFERENCE = "INFERENCE"       # Derived from data analysis (future: LLM)
    CIO_OPINION = "CIO_OPINION"  # Synthesized investment view (future: LLM)

class EvidenceDomain(str, Enum):
    """Subject domain of evidence — what area of analysis this evidence supports.

    This is separate from EvidenceTag, which classifies the TYPE of evidence.
    EvidenceDomain classifies the SUBJECT matter for analyst-specific filtering.
    """

    FINANCIAL = "FINANCIAL"
    BUSINESS = "BUSINESS"
    ASSET_QUALITY = "ASSET_QUALITY"

class EvidenceItem(BaseModel):
    """A single piece of evidence supporting a metric, finding, or conclusion.

    Attributes:
        evidence_id: Unique identifier (UUID) for cross-referencing.
        tag: Classification of the evidence type.
        label: Human-readable description of this evidence.
        source: Origin of the data (e.g., "HDFC Bank Annual Report FY2025").
        source_field: Specific field path (e.g., "balance_sheet.total_equity").
        source_url: Link to external source document or page.
        publication_date: When the source material was published.
        retrieved_at: When the data was fetched/captured by InvestIQ.
        timestamp: When this evidence item was created.
        value: The actual data point or computed result.
    """

    evidence_id: str = Field(description="UUID for cross-referencing")
    tag: EvidenceTag
    label: str
    source: str
    source_field: str | None = None
    source_url: str | None = None
    publication_date: date | None = None
    retrieved_at: datetime | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    value: Any = None
    domain: EvidenceDomain | None = None
