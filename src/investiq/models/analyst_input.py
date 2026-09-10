"""Analyst input payload model.

Compacts metrics and evidence into a structured payload for LLM prompts,
preventing token bloat by avoiding sending full raw financial statements.
"""

from pydantic import BaseModel, Field

from investiq.models.company import CompanyProfile
from investiq.models.evidence import EvidenceItem
from investiq.models.metrics import BankMetrics


class AnalystInput(BaseModel):
    """Input provided to an analyst prompt.

    Attributes:
        company: Identification and classification of target company.
        latest_metrics: Most recent calculated metrics (e.g., FY2025).
        prior_metrics: Optional prior year metrics for trend analysis.
        evidence_items: Selected evidence items applicable to this research.
        research_objective: Target research goal/question for the analyst.
    """

    company: CompanyProfile
    latest_metrics: BankMetrics
    prior_metrics: BankMetrics | None = None
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    research_objective: str = "Analyze bank fundamentals, asset quality, and investment implications."
