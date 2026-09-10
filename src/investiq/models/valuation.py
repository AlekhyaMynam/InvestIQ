"""Valuation models for equity research.

Supports multiple valuation methods with explicit assumptions
and evidence traceability. For banks, the initial approach uses
P/B × ROE and P/E methods.
"""

from enum import Enum

from pydantic import BaseModel

from investiq.models.evidence import EvidenceItem


class ValuationMethod(str, Enum):
    """Supported valuation methodologies."""

    PB_ROE = "pb_roe"             # Justified P/B via Gordon Growth Model
    PE = "pe"                     # Justified P/E via earnings model
    # Future: RESIDUAL_INCOME, DCF, EV_EBITDA


class ValuationResult(BaseModel):
    """Result of a single valuation method.

    Attributes:
        method: Which valuation methodology was used.
        estimated_fair_value: Calculated fair value per share in ₹.
        current_price: Current market price per share in ₹.
        upside_pct: (fair_value - current_price) / current_price × 100.
        assumptions: Explicitly stated assumptions (tagged ASSUMPTION).
        evidence: Calculations and facts supporting the result.
    """

    method: ValuationMethod
    estimated_fair_value: float
    current_price: float
    upside_pct: float
    assumptions: list[EvidenceItem]
    evidence: list[EvidenceItem]


class ValuationSummary(BaseModel):
    """Aggregated valuation across all methods.

    Attributes:
        methods: Individual valuation results.
        blended_fair_value: Weighted average fair value in ₹.
        verdict: Human-readable assessment.
        pb_weight: Weight assigned to P/B method (0–1).
        pe_weight: Weight assigned to P/E method (0–1).
    """

    methods: list[ValuationResult]
    blended_fair_value: float
    verdict: str                   # "Undervalued" | "Fairly Valued" | "Overvalued"
    pb_weight: float = 0.6
    pe_weight: float = 0.4
