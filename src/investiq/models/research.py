"""Research models — snapshots, findings, deltas, and status tracking.

ResearchSnapshot is the primary output artifact of the InvestIQ pipeline.
ResearchDelta powers the "What Changed?" signature feature.
ResearchFinding supports structured analyst conclusions with evidence links.
ResearchStatus enables future UI progress tracking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from investiq.models.company import CompanyProfile
from investiq.models.evidence import EvidenceItem
from investiq.models.financials import FinancialData
from investiq.models.metrics import BankMetrics
from investiq.models.synthesis import CIOSynthesis
from investiq.models.valuation import ValuationSummary


class FindingCategory(str, Enum):
    """Categories for research findings."""

    PROFITABILITY = "profitability"
    ASSET_QUALITY = "asset_quality"
    GROWTH = "growth"
    VALUATION = "valuation"
    CAPITAL_ADEQUACY = "capital_adequacy"
    LIABILITY_FRANCHISE = "liability_franchise"
    RISK = "risk"
    COMPETITIVE_POSITION = "competitive_position"


class ResearchFinding(BaseModel):
    """A structured research finding or conclusion.

    Links analyst conclusions to the evidence that supports them,
    enabling drill-down from conclusions to source data.

    Attributes:
        analyst: Which analyst or agent produced this finding.
        title: Short title summarizing the finding.
        statement: Full statement of the finding.
        confidence: Confidence level (0.0 = low, 1.0 = high).
        evidence_ids: UUIDs linking to EvidenceItem.evidence_id.
        category: Classification of the finding.
        fundamental_observation: Core business observation.
        why_it_matters: Analytical justification of significance.
        positive_implication: Upside driver or competitive advantage.
        negative_implication: Downside risk or counter-evidence.
        thesis_breaker: Condition under which this thesis fails.
    """

    analyst: str
    title: str
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str]
    category: FindingCategory

    # Extended structured analysis fields
    fundamental_observation: str | None = None
    why_it_matters: str | None = None
    positive_implication: str | None = None
    negative_implication: str | None = None
    thesis_breaker: str | None = None


class ResearchFindingResponse(BaseModel):
    """Wrapper for a list of research findings returned by an LLM.

    Enables Gemini structured-output schema enforcement by wrapping
    list[ResearchFinding] in a BaseModel that has model_json_schema().
    """

    findings: list[ResearchFinding]


class ResearchSnapshot(BaseModel):
    """Timestamped research output — the core artifact of InvestIQ.

    Contains everything needed to reproduce, audit, or compare
    research on a company at a point in time.
    """

    snapshot_id: str                   # UUID
    ticker: str
    company: CompanyProfile
    generated_at: datetime
    financial_data: FinancialData
    metrics: list[BankMetrics]         # Multi-year
    valuation: ValuationSummary
    findings: list[ResearchFinding]    # Structured conclusions
    evidence_chain: list[EvidenceItem] # Full audit trail
    cio_synthesis: CIOSynthesis | None = None
    metadata: dict = Field(default_factory=dict)


class MetricChange(BaseModel):
    """A single metric that changed between two research snapshots."""

    metric_name: str
    previous_value: Any
    current_value: Any
    change_pct: float | None = None
    significance: str = "minor"        # "material" | "minor"


class ResearchDelta(BaseModel):
    """Comparison between two research snapshots.

    Powers the "What Changed?" signature feature.
    """

    ticker: str
    previous_snapshot_id: str
    current_snapshot_id: str
    previous_date: datetime
    current_date: datetime
    metric_changes: list[MetricChange]
    new_data_periods: list[str]
    valuation_change: dict
    summary: str


class ResearchStatusEnum(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    LOADING_DATA = "loading_data"
    CALCULATING_METRICS = "calculating_metrics"
    CALCULATING_VALUATION = "calculating_valuation"
    GENERATING_FINDINGS = "generating_findings"
    COMPLETE = "complete"
    ERROR = "error"


class ResearchStatus(BaseModel):
    """Tracks research pipeline progress for UI updates.

    Attributes:
        ticker: Company being researched.
        status: Current pipeline stage.
        current_step: Human-readable description of current activity.
        progress_pct: Estimated progress (0–100).
        started_at: When research was initiated.
        completed_at: When research finished (or errored).
        error_message: Error details if status is ERROR.
    """

    ticker: str
    status: ResearchStatusEnum
    current_step: str | None = None
    progress_pct: float | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error_message: str | None = None
