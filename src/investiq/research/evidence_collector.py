"""EvidenceCollector — deterministically combines evidence from multiple sources.

The collector aggregates evidence from:
1. Supplied evidence items (e.g., from synthetic fixture or external sources)
2. Latest bank metrics evidence (deterministic calculations)
3. Valuation evidence (P/B × ROE, P/E — calculations and assumptions)

Every EvidenceItem retains its original provenance. No LLM calls, no web
fetching, no invented evidence.
"""

from __future__ import annotations

from investiq.models.evidence import EvidenceItem
from investiq.models.metrics import BankMetrics
from investiq.models.valuation import ValuationSummary

from .evidence import EvidenceSet


class EvidenceCollector:
    """Deterministic collector that assembles a single EvidenceSet from
    multiple evidence sources.

    The collector never calls an LLM, never fetches external data,
    and never invents evidence.
    """

    @staticmethod
    def collect(
        supplied_evidence: list[EvidenceItem] | None = None,
        metrics: BankMetrics | None = None,
        valuation: ValuationSummary | None = None,
    ) -> EvidenceSet:
        """Combine evidence from supplied items, bank metrics, and valuation.

        Args:
            supplied_evidence: Externally supplied evidence items (e.g., fixture).
            metrics: The latest BankMetrics containing calculated-metric evidence.
            valuation: A ValuationSummary with method-level evidence and assumptions.

        Returns:
            An EvidenceSet with all evidence combined, deduplicated, and
            conflict-checked.

        Raises:
            EvidenceConflictError: If the same evidence_id appears with
                                   conflicting content across sources.
        """
        result: list[EvidenceItem] = []

        # 1. Supplied evidence
        if supplied_evidence:
            result.extend(supplied_evidence)

        # 2. Bank metrics evidence
        if metrics is not None and metrics.evidence:
            result.extend(metrics.evidence)

        # 3. Valuation evidence
        if valuation is not None:
            for method in valuation.methods:
                if method.evidence:
                    result.extend(method.evidence)
                if method.assumptions:
                    result.extend(method.assumptions)

        return EvidenceSet(evidence=result)