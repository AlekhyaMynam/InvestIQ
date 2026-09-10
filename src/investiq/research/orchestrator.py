"""Research orchestration — coordinates deterministic calculations with LLM analysis.

Combines financial data loading, metric calculation, bank valuation,
and the FinancialAnalystPipeline into a single orchestrated flow
that produces a ResearchSnapshot.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from investiq.analysts.asset_quality_analyst import AssetQualityAnalyst
from investiq.analysts.banking_business_analyst import BankingBusinessAnalyst
from investiq.analysts.executor import AnalystExecutor
from investiq.analysts.financial_analyst import FinancialAnalystPipeline
from investiq.analysts.registry import AnalystRegistry
from investiq.calculators.bank_metrics import compute_bank_metrics
from investiq.calculators.bank_valuation import compute_bank_valuation
from investiq.data.loader import load_financial_data
from investiq.llm.base import LLMProvider
from investiq.models.analyst_input import AnalystInput
from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag
from investiq.models.financials import FinancialData
from investiq.models.research import ResearchFinding, ResearchSnapshot
from investiq.synthesis.cio import CIOSynthesizer

from .evidence import EvidenceSet
from .evidence_collector import EvidenceCollector


# Tags relevant to the financial/banking analyst pipeline.
# These evidence categories provide useful context for fundamental analysis
# of banking companies. INFERENCE and CIO_OPINION are excluded because
# they represent future LLM-derived outputs, not deterministic evidence.
_ANALYST_RELEVANT_TAGS = {
    EvidenceTag.FACT,
    EvidenceTag.CALCULATION,
    EvidenceTag.ASSUMPTION,
}

# Analyst-specific evidence domain mapping.
# Each analyst key maps to the EvidenceDomain(s) relevant to their analysis.
_ANALYST_EVIDENCE_DOMAINS: dict[str, set[EvidenceDomain]] = {
    "financial_analyst": {EvidenceDomain.FINANCIAL},
    "asset_quality_analyst": {EvidenceDomain.ASSET_QUALITY},
    "banking_business_analyst": {EvidenceDomain.FINANCIAL, EvidenceDomain.BUSINESS},
}


class ResearchOrchestrator:
    """Orchestrates the full research pipeline for a single ticker.

    Coordinates deterministic calculations (metrics, valuation) with
    LLM-based analysis (FinancialAnalystPipeline) to produce a
    ResearchSnapshot.

    The orchestrator does NOT perform financial calculations or
    generate prompts itself — it delegates to existing components.

    Attributes:
        provider: LLMProvider for the FinancialAnalystPipeline.
        data_dir: Directory containing prepared financial data JSON files.
    """

    def __init__(
        self,
        provider: LLMProvider,
        data_dir: str | Path | None = None,
        analyst_registry: AnalystRegistry | None = None,
        analyst_executor: AnalystExecutor | None = None,
        cio_synthesizer: CIOSynthesizer | None = None,
    ) -> None:
        self.provider = provider
        self.data_dir = Path(data_dir) if data_dir else None

        if analyst_registry is not None:
            self.analyst_registry = analyst_registry
        else:
            default_registry = AnalystRegistry()
            default_registry.register(
                "financial_analyst",
                FinancialAnalystPipeline(provider=provider),
            )
            default_registry.register(
                "asset_quality_analyst",
                AssetQualityAnalyst(provider=provider),
            )
            default_registry.register(
                "banking_business_analyst",
                BankingBusinessAnalyst(provider=provider),
            )
            self.analyst_registry = default_registry

        if analyst_executor is not None:
            self.analyst_executor = analyst_executor
        else:
            self.analyst_executor = AnalystExecutor(registry=self.analyst_registry)

        if cio_synthesizer is not None:
            self.cio_synthesizer = cio_synthesizer
        else:
            self.cio_synthesizer = CIOSynthesizer(provider=provider)

    def research(
        self,
        ticker: str,
        evidence_items: list[EvidenceItem] | None = None,
        research_objective: str = "Analyze bank fundamentals, asset quality, and investment implications.",
    ) -> ResearchSnapshot:
        """Execute the full research pipeline for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "HDFCBANK").
            evidence_items: Evidence items for the analyst. If None,
                            a default set should be provided by the caller
                            or loaded from a fixture.
            research_objective: Target research goal for the analyst.

        Returns:
            ResearchSnapshot containing all computed and analysed data.

        Raises:
            FileNotFoundError: If no prepared data exists for the ticker.
            ValueError: If data validation fails.
        """
        # 1. Load financial data
        financial_data = load_financial_data(ticker, self.data_dir)

        # 2. Compute deterministic bank metrics (all years)
        metrics_list = compute_bank_metrics(financial_data)

        # 3. Compute bank valuation from the latest year's metrics
        latest_metrics = metrics_list[-1]
        market_data = financial_data.market_data
        latest_income = financial_data.income_statements[-1]

        valuation = compute_bank_valuation(
            latest_metrics=latest_metrics,
            current_price=market_data.current_price,
            dividend_per_share=latest_income.dividend_per_share,
        )

        # 4. Build the full evidence set using the collector
        full_evidence_set = EvidenceCollector.collect(
            supplied_evidence=evidence_items,
            metrics=latest_metrics,
            valuation=valuation,
        )

        # 5. Filter evidence by tag (shared across all analysts)
        #    Use only FACT, CALCULATION, and ASSUMPTION tags.
        #    This is deterministic — no LLM involved.
        tag_filtered_evidence = [
            item
            for item in full_evidence_set
            if item.tag in _ANALYST_RELEVANT_TAGS
        ]

        # 6. Build analyst-specific evidence and execute each analyst
        #    Each analyst receives only evidence matching their domain(s).
        analyst_keys = ["financial_analyst", "asset_quality_analyst", "banking_business_analyst"]
        all_findings: list[ResearchFinding] = []

        for key in analyst_keys:
            domains = _ANALYST_EVIDENCE_DOMAINS.get(key, set())
            analyst_evidence = [
                item for item in tag_filtered_evidence
                if item.domain is None or item.domain in domains
            ]

            analyst_input = AnalystInput(
                company=financial_data.company,
                latest_metrics=latest_metrics,
                prior_metrics=metrics_list[-2] if len(metrics_list) >= 2 else None,
                evidence_items=analyst_evidence,
                research_objective=research_objective,
            )

            analyst_findings = self.analyst_executor.execute(
                [key],
                analyst_input,
            )
            all_findings.extend(analyst_findings)

        findings = all_findings

        # 7. Run CIO synthesis on the completed research
        cio_synthesis = None
        if findings:
            # Build a temporary snapshot to pass to the CIO synthesizer
            temp_snapshot = ResearchSnapshot(
                snapshot_id="temp",
                ticker=ticker.upper(),
                company=financial_data.company,
                generated_at=datetime.now(timezone.utc),
                financial_data=financial_data,
                metrics=metrics_list,
                valuation=valuation,
                findings=findings,
                evidence_chain=full_evidence_set.to_list(),
            )
            try:
                cio_synthesis = self.cio_synthesizer.synthesize(temp_snapshot)
            except Exception:
                # CIO synthesis is non-critical — continue without it
                pass

        # 8. Assemble evidence chain from the full deduplicated set
        evidence_chain = full_evidence_set.to_list()

        # 9. Build and return the ResearchSnapshot
        snapshot = ResearchSnapshot(
            snapshot_id=str(uuid.uuid4()),
            ticker=ticker.upper(),
            company=financial_data.company,
            generated_at=datetime.now(timezone.utc),
            financial_data=financial_data,
            metrics=metrics_list,
            valuation=valuation,
            findings=findings,
            evidence_chain=evidence_chain,
            cio_synthesis=cio_synthesis,
            metadata={
                "research_objective": research_objective,
                "num_findings": len(findings),
                "num_metrics_years": len(metrics_list),
            },
        )

        return snapshot