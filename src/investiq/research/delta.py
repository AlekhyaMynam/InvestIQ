"""ResearchDeltaCalculator — deterministic comparison of two ResearchSnapshot objects.

Computes what changed between an older and newer snapshot for the same ticker.
All calculations are deterministic, use zero LLM calls, and produce a validated
ResearchDelta instance.

Usage:
    delta = ResearchDeltaCalculator.compare(previous_snapshot, current_snapshot)
"""

from __future__ import annotations

from investiq.models.metrics import BankMetrics
from investiq.models.research import (
    MetricChange,
    ResearchDelta,
    ResearchSnapshot,
)


# Metric fields to compare from BankMetrics.
# Each entry is (field_name, display_label).
_METRIC_FIELDS = [
    ("roe", "ROE"),
    ("roa", "ROA"),
    ("nim", "NIM"),
    ("casa_ratio", "CASA Ratio"),
    ("gross_npa_ratio", "Gross NPA Ratio"),
    ("net_npa_ratio", "Net NPA Ratio"),
    ("cost_to_income", "Cost-to-Income"),
    ("credit_cost", "Credit Cost"),
    ("eps", "EPS"),
    ("book_value_per_share", "Book Value Per Share"),
]


def _change_pct(prev: float, curr: float) -> float | None:
    """Compute ((curr - prev) / abs(prev)) * 100. Returns None if prev is zero."""
    if prev == 0.0:
        return None
    return ((curr - prev) / abs(prev)) * 100


def _determine_significance(
    change_pct: float | None,
    prev: float,
    curr: float,
) -> str:
    """material if abs(change_pct) >= 10 or absolute diff >= 0.01 when pct is None."""
    if change_pct is not None:
        return "material" if abs(change_pct) >= 10.0 else "minor"
    return "material" if abs(curr - prev) >= 0.01 else "minor"


def _metrics_by_year(metrics: list[BankMetrics]) -> dict[str, BankMetrics]:
    """Index metrics by fiscal_year for quick lookup."""
    return {m.fiscal_year: m for m in metrics}


def _build_summary(
    metric_changes: list[MetricChange],
    new_periods: list[str],
    valuation_change: dict,
) -> str:
    """Generate a deterministic, human-readable summary. No LLM involved."""
    parts: list[str] = []

    material = [mc for mc in metric_changes if mc.significance == "material"]
    minor = [mc for mc in metric_changes if mc.significance == "minor"]

    if not metric_changes and not new_periods:
        return "No material changes were identified between the two research snapshots."

    for mc in material:
        pv = mc.previous_value
        cv = mc.current_value
        if mc.change_pct is not None:
            parts.append(
                f"{mc.metric_name} changed from {pv} to {cv} "
                f"({mc.change_pct:+.1f}%)."
            )
        else:
            parts.append(f"{mc.metric_name} changed from {pv} to {cv}.")
    if minor:
        parts.append(f"{len(minor)} other metric(s) had only minor changes.")
    if new_periods:
        parts.append(f"New data period(s) detected: {', '.join(new_periods)}.")

    v_prev = valuation_change.get("previous_blended_fair_value")
    v_curr = valuation_change.get("current_blended_fair_value")
    v_pct = valuation_change.get("blended_fair_value_change_pct")
    v_prev_verdict = valuation_change.get("previous_verdict", "")
    v_curr_verdict = valuation_change.get("current_verdict", "")

    if v_prev is not None and v_curr is not None:
        if v_pct is not None:
            parts.append(
                f"Blended fair value changed from ₹{v_prev} to ₹{v_curr} "
                f"({v_pct:+.1f}%)."
            )
        else:
            parts.append(
                f"Blended fair value changed from ₹{v_prev} to ₹{v_curr}."
            )
    if v_prev_verdict != v_curr_verdict and v_prev_verdict and v_curr_verdict:
        parts.append(f"Verdict changed from {v_prev_verdict} to {v_curr_verdict}.")

    return " ".join(parts)
class ResearchDeltaCalculator:
    """Deterministic comparator for ResearchSnapshot objects.

    Produces a ResearchDelta describing what changed between two snapshots
    for the same company ticker. Never calls an LLM.
    """

    @staticmethod
    def compare(
        previous: ResearchSnapshot,
        current: ResearchSnapshot,
    ) -> ResearchDelta:
        """Compare two snapshots and produce a ResearchDelta.

        Args:
            previous: The older ResearchSnapshot.
            current:  The newer ResearchSnapshot.

        Returns:
            A fully populated ResearchDelta.

        Raises:
            ValueError: If snapshots are incompatible (different ticker,
                        same snapshot_id, or current not newer than previous).
        """
        # ── Validation ──────────────────────────────────────────────
        prev_ticker = previous.ticker.strip().upper()
        curr_ticker = current.ticker.strip().upper()
        if prev_ticker != curr_ticker:
            raise ValueError(
                f"Cannot compare snapshots for different tickers: "
                f"previous={previous.ticker!r}, current={current.ticker!r}"
            )

        if previous.snapshot_id == current.snapshot_id:
            raise ValueError(
                f"Cannot compare a snapshot with itself: "
                f"{previous.snapshot_id!r}"
            )

        if previous.generated_at >= current.generated_at:
            raise ValueError(
                f"Previous snapshot ({previous.generated_at}) must be older "
                f"than current snapshot ({current.generated_at})"
            )

        # ── Metrics comparison ──────────────────────────────────────
        prev_by_year = _metrics_by_year(previous.metrics)
        curr_by_year = _metrics_by_year(current.metrics)

        common_years = sorted(
            set(prev_by_year.keys()) & set(curr_by_year.keys())
        )
        new_periods = sorted(
            set(curr_by_year.keys()) - set(prev_by_year.keys())
        )

        metric_changes: list[MetricChange] = []

        for field_name, display_name in _METRIC_FIELDS:
            for fy in common_years:
                prev_val = getattr(prev_by_year[fy], field_name)
                curr_val = getattr(curr_by_year[fy], field_name)
                if prev_val == curr_val:
                    continue
                pct = _change_pct(prev_val, curr_val)
                significance = _determine_significance(pct, prev_val, curr_val)
                metric_changes.append(MetricChange(
                    metric_name=f"{display_name} ({fy})",
                    previous_value=prev_val,
                    current_value=curr_val,
                    change_pct=pct,
                    significance=significance,
                ))

        # ── Valuation comparison ────────────────────────────────────
        v_prev = previous.valuation
        v_curr = current.valuation
        v_prev_val = v_prev.blended_fair_value
        v_curr_val = v_curr.blended_fair_value
        v_change = v_curr_val - v_prev_val
        v_change_pct = _change_pct(v_prev_val, v_curr_val)

        valuation_change: dict = {
            "previous_blended_fair_value": v_prev_val,
            "current_blended_fair_value": v_curr_val,
            "blended_fair_value_change": v_change,
            "blended_fair_value_change_pct": v_change_pct,
            "previous_verdict": v_prev.verdict,
            "current_verdict": v_curr.verdict,
        }

        # ── Build summary ───────────────────────────────────────────
        summary = _build_summary(metric_changes, new_periods, valuation_change)

        # ── Assemble delta ──────────────────────────────────────────
        return ResearchDelta(
            ticker=curr_ticker,
            previous_snapshot_id=previous.snapshot_id,
            current_snapshot_id=current.snapshot_id,
            previous_date=previous.generated_at,
            current_date=current.generated_at,
            metric_changes=metric_changes,
            new_data_periods=new_periods,
            valuation_change=valuation_change,
            summary=summary,
        )