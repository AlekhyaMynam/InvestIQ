"""Bank valuation using P/B × ROE and P/E methods.

All calculations are deterministic Python. Assumptions (cost of equity,
growth rate) are explicitly stated and tagged as ASSUMPTION in the
evidence chain.

Valuation methods:
    1. P/B × ROE (Gordon Growth Model for banks):
       - Sustainable growth (g) = Retention Ratio × ROE
       - Justified P/B = (ROE - g) / (CoE - g)
       - Fair Value = Justified P/B × BVPS

    2. P/E (Earnings-based):
       - Justified P/E = Payout Ratio / (CoE - g)
       - Fair Value = Justified P/E × EPS

    3. Blended: Weighted average (default 60% P/B, 40% P/E)
"""

import uuid
from datetime import datetime, timezone

from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag
from investiq.models.metrics import BankMetrics
from investiq.models.valuation import (
    ValuationMethod,
    ValuationResult,
    ValuationSummary,
)


# Default assumptions for Indian private sector banks
DEFAULT_COST_OF_EQUITY = 0.135   # 13.5%
DEFAULT_PB_WEIGHT = 0.6
DEFAULT_PE_WEIGHT = 0.4


def _assumption(label: str, value: float) -> EvidenceItem:
    """Create an ASSUMPTION evidence item."""
    return EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        tag=EvidenceTag.ASSUMPTION,
        label=label,
        source="InvestIQ Valuation Model — MVP Default",
        timestamp=datetime.now(timezone.utc),
        value=value,
        domain=EvidenceDomain.FINANCIAL,
    )


def _calc_evidence(label: str, value: float) -> EvidenceItem:
    """Create a CALCULATION evidence item."""
    return EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        tag=EvidenceTag.CALCULATION,
        label=label,
        source="InvestIQ Bank Valuation Calculator",
        timestamp=datetime.now(timezone.utc),
        value=round(value, 4),
        domain=EvidenceDomain.FINANCIAL,
    )


def calculate_sustainable_growth(
    roe_pct: float,
    dividend_payout_ratio: float,
) -> float:
    """Sustainable growth rate = Retention Ratio × ROE.

    Args:
        roe_pct: Return on Equity as percentage (e.g., 16.0 for 16%).
        dividend_payout_ratio: Dividends / Net Profit as decimal (0–1).

    Returns:
        Sustainable growth rate as decimal (e.g., 0.10 for 10%).
    """
    retention_ratio = 1.0 - dividend_payout_ratio
    roe_decimal = roe_pct / 100
    return retention_ratio * roe_decimal


def calculate_dividend_payout_ratio(
    dividend_per_share: float | None,
    eps: float,
) -> float:
    """Dividend Payout Ratio = DPS / EPS.

    Returns a value between 0 and 1. Returns 0 if DPS is not available
    or EPS is zero/negative.
    """
    if dividend_per_share is None or eps <= 0:
        return 0.0
    ratio = dividend_per_share / eps
    # Cap at 1.0 (payout can't exceed earnings in steady state)
    return min(ratio, 1.0)


def calculate_pb_roe_valuation(
    roe_pct: float,
    bvps: float,
    current_price: float,
    sustainable_growth: float,
    cost_of_equity: float = DEFAULT_COST_OF_EQUITY,
) -> ValuationResult:
    """P/B × ROE valuation using Gordon Growth Model adaptation.

    Justified P/B = (ROE - g) / (CoE - g)
    Fair Value = Justified P/B × BVPS

    Guards against:
    - CoE <= g (would produce negative/infinite P/B)
    - Negative ROE
    """
    assumptions = [
        _assumption(f"Cost of Equity = {cost_of_equity * 100:.1f}%", cost_of_equity),
        _assumption(f"Sustainable Growth Rate = {sustainable_growth * 100:.2f}%", sustainable_growth),
    ]
    evidence = []

    roe_decimal = roe_pct / 100

    # Guard: if cost of equity <= growth, the model breaks down
    if cost_of_equity <= sustainable_growth:
        # Fall back to simple ROE/CoE ratio
        justified_pb = roe_decimal / cost_of_equity
        evidence.append(_calc_evidence(
            f"Justified P/B (fallback: ROE/CoE) = {justified_pb:.2f}",
            justified_pb,
        ))
    else:
        justified_pb = (roe_decimal - sustainable_growth) / (cost_of_equity - sustainable_growth)
        evidence.append(_calc_evidence(
            f"Justified P/B = (ROE - g) / (CoE - g) = ({roe_decimal:.4f} - {sustainable_growth:.4f}) / ({cost_of_equity:.4f} - {sustainable_growth:.4f}) = {justified_pb:.2f}",
            justified_pb,
        ))

    fair_value = justified_pb * bvps
    evidence.append(_calc_evidence(
        f"Fair Value = Justified P/B × BVPS = {justified_pb:.2f} × ₹{bvps:.2f} = ₹{fair_value:.2f}",
        fair_value,
    ))

    upside = ((fair_value - current_price) / current_price) * 100 if current_price > 0 else 0.0

    return ValuationResult(
        method=ValuationMethod.PB_ROE,
        estimated_fair_value=round(fair_value, 2),
        current_price=current_price,
        upside_pct=round(upside, 2),
        assumptions=assumptions,
        evidence=evidence,
    )


def calculate_pe_valuation(
    eps: float,
    current_price: float,
    dividend_payout_ratio: float,
    sustainable_growth: float,
    cost_of_equity: float = DEFAULT_COST_OF_EQUITY,
) -> ValuationResult:
    """P/E valuation using justified P/E from earnings model.

    Justified P/E = Payout Ratio / (CoE - g)
    Fair Value = Justified P/E × EPS

    Guards against:
    - CoE <= g (would produce negative/infinite P/E)
    - Non-positive EPS
    """
    assumptions = [
        _assumption(f"Cost of Equity = {cost_of_equity * 100:.1f}%", cost_of_equity),
        _assumption(f"Sustainable Growth Rate = {sustainable_growth * 100:.2f}%", sustainable_growth),
        _assumption(f"Dividend Payout Ratio = {dividend_payout_ratio * 100:.2f}%", dividend_payout_ratio),
    ]
    evidence = []

    if eps <= 0 or cost_of_equity <= sustainable_growth:
        # Cannot compute meaningful P/E
        return ValuationResult(
            method=ValuationMethod.PE,
            estimated_fair_value=0.0,
            current_price=current_price,
            upside_pct=0.0,
            assumptions=assumptions,
            evidence=[_calc_evidence("P/E valuation not applicable (EPS <= 0 or CoE <= g)", 0.0)],
        )

    justified_pe = dividend_payout_ratio / (cost_of_equity - sustainable_growth)
    evidence.append(_calc_evidence(
        f"Justified P/E = Payout / (CoE - g) = {dividend_payout_ratio:.4f} / ({cost_of_equity:.4f} - {sustainable_growth:.4f}) = {justified_pe:.2f}",
        justified_pe,
    ))

    fair_value = justified_pe * eps
    evidence.append(_calc_evidence(
        f"Fair Value = Justified P/E × EPS = {justified_pe:.2f} × ₹{eps:.2f} = ₹{fair_value:.2f}",
        fair_value,
    ))

    upside = ((fair_value - current_price) / current_price) * 100 if current_price > 0 else 0.0

    return ValuationResult(
        method=ValuationMethod.PE,
        estimated_fair_value=round(fair_value, 2),
        current_price=current_price,
        upside_pct=round(upside, 2),
        assumptions=assumptions,
        evidence=evidence,
    )


def _determine_verdict(upside_pct: float) -> str:
    """Map upside percentage to a human-readable verdict."""
    if upside_pct > 15:
        return "Undervalued"
    elif upside_pct < -15:
        return "Overvalued"
    else:
        return "Fairly Valued"


def compute_bank_valuation(
    latest_metrics: BankMetrics,
    current_price: float,
    dividend_per_share: float | None = None,
    cost_of_equity: float = DEFAULT_COST_OF_EQUITY,
    pb_weight: float = DEFAULT_PB_WEIGHT,
    pe_weight: float = DEFAULT_PE_WEIGHT,
) -> ValuationSummary:
    """Compute blended bank valuation using P/B × ROE and P/E methods.

    Args:
        latest_metrics: Most recent year's calculated bank metrics.
        current_price: Current market price per share (₹).
        dividend_per_share: Most recent DPS (₹). None if not available.
        cost_of_equity: Assumed cost of equity (decimal, e.g., 0.135).
        pb_weight: Weight for P/B method in blended value (0–1).
        pe_weight: Weight for P/E method in blended value (0–1).

    Returns:
        ValuationSummary with individual method results and blended fair value.
    """
    # Calculate payout ratio and sustainable growth
    payout_ratio = calculate_dividend_payout_ratio(
        dividend_per_share, latest_metrics.eps
    )
    sustainable_growth = calculate_sustainable_growth(
        latest_metrics.roe, payout_ratio
    )

    # P/B × ROE valuation
    pb_result = calculate_pb_roe_valuation(
        roe_pct=latest_metrics.roe,
        bvps=latest_metrics.book_value_per_share,
        current_price=current_price,
        sustainable_growth=sustainable_growth,
        cost_of_equity=cost_of_equity,
    )

    # P/E valuation
    pe_result = calculate_pe_valuation(
        eps=latest_metrics.eps,
        current_price=current_price,
        dividend_payout_ratio=payout_ratio,
        sustainable_growth=sustainable_growth,
        cost_of_equity=cost_of_equity,
    )

    # Blended fair value
    methods = [pb_result, pe_result]
    blended = (
        pb_weight * pb_result.estimated_fair_value
        + pe_weight * pe_result.estimated_fair_value
    )
    blended = round(blended, 2)

    blended_upside = (
        ((blended - current_price) / current_price) * 100
        if current_price > 0
        else 0.0
    )

    return ValuationSummary(
        methods=methods,
        blended_fair_value=blended,
        verdict=_determine_verdict(blended_upside),
        pb_weight=pb_weight,
        pe_weight=pe_weight,
    )
