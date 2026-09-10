"""CIO Synthesizer — synthesizes analyst findings into a coherent investment thesis.

The CIO runs after all three analysts have produced findings and produces
a structured CIOSynthesis with executive summary, scenarios, and assessment.

This is NOT a ResearchAnalyst — it is a synthesis component that operates
on the completed ResearchSnapshot.
"""

from __future__ import annotations

from typing import Any

from investiq.llm.base import LLMProvider, LLMRequest, LLMResponse
from investiq.llm.cache import LLMCache, build_cache_key
from investiq.llm.cost import CostTracker
from investiq.models.research import ResearchFinding, ResearchSnapshot
from investiq.models.synthesis import CIOSynthesis, CIOSynthesisResponse
from investiq.prompts.cio_synthesis import (
    CIO_SYNTHESIS_SYSTEM_INSTRUCTION,
    PROMPT_VERSION,
    render_cio_synthesis_prompt,
)


_CIO_MODEL_CONFIG = {"temperature": 0.3, "max_tokens": 1500}


def _format_findings(findings: list[ResearchFinding]) -> str:
    """Format analyst findings into a text block for the prompt."""
    lines: list[str] = []
    for f in findings:
        enrichment = []
        if f.fundamental_observation:
            enrichment.append(f"Observation: {f.fundamental_observation}")
        if f.why_it_matters:
            enrichment.append(f"Why: {f.why_it_matters}")
        if f.positive_implication:
            enrichment.append(f"Positive: {f.positive_implication}")
        if f.negative_implication:
            enrichment.append(f"Negative: {f.negative_implication}")
        if f.thesis_breaker:
            enrichment.append(f"Thesis Breaker: {f.thesis_breaker}")

        enrichment_str = "\n      ".join(enrichment) if enrichment else ""
        enrichment_block = f"\n      {enrichment_str}" if enrichment_str else ""

        lines.append(
            f"  [{f.category.value}] {f.analyst} (confidence: {f.confidence:.2f})\n"
            f"    Title: {f.title}\n"
            f"    Statement: {f.statement}\n"
            f"    Evidence IDs: {f.evidence_ids}{enrichment_block}"
        )
    return "\n".join(lines)


class CIOSynthesizer:
    """Synthesizes analyst findings into a structured investment thesis.

    Uses the existing LLM infrastructure (provider, cache, cost tracker)
    but is NOT a ResearchAnalyst — it operates on the completed ResearchSnapshot.

    Attributes:
        provider: LLMProvider implementation (e.g., MockLLMProvider).
        cache: Optional LLMCache for caching responses.
        cost_tracker: Optional CostTracker for tracking token usage & costs.
    """

    def __init__(
        self,
        provider: LLMProvider,
        cache: LLMCache | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.cost_tracker = cost_tracker or CostTracker()

    def synthesize(
        self,
        snapshot: ResearchSnapshot,
    ) -> CIOSynthesis:
        """Produce a CIO synthesis from the completed research snapshot.

        Args:
            snapshot: A completed ResearchSnapshot with all analyst findings.

        Returns:
            A validated CIOSynthesis instance.

        Raises:
            ValueError: If the snapshot has no metrics.
        """
        metrics = snapshot.metrics[-1] if snapshot.metrics else None
        if metrics is None:
            raise ValueError("Cannot synthesize: snapshot has no metrics.")

        findings_text = _format_findings(snapshot.findings)
        prompt_text = render_cio_synthesis_prompt(
            ticker=snapshot.ticker,
            company_name=snapshot.company.name,
            fiscal_year=metrics.fiscal_year,
            roe=metrics.roe, roa=metrics.roa, nim=metrics.nim,
            casa_ratio=metrics.casa_ratio,
            gross_npa_ratio=metrics.gross_npa_ratio,
            net_npa_ratio=metrics.net_npa_ratio,
            cost_to_income=metrics.cost_to_income,
            credit_cost=metrics.credit_cost,
            eps=metrics.eps,
            book_value_per_share=metrics.book_value_per_share,
            blended_fair_value=snapshot.valuation.blended_fair_value,
            verdict=snapshot.valuation.verdict,
            findings_text=findings_text,
        )

        normalized_input = snapshot.model_dump_json(exclude={"cio_synthesis"})
        cache_key = build_cache_key(
            ticker=snapshot.ticker,
            analyst_type="cio_synthesis",
            normalized_input=normalized_input,
            prompt_version=PROMPT_VERSION,
            model_config=_CIO_MODEL_CONFIG,
        )

        if self.cache is not None:
            cached_resp = self.cache.get(cache_key)
            if cached_resp is not None:
                self.cost_tracker.record_call(
                    model=cached_resp.model,
                    input_tokens=cached_resp.input_tokens,
                    output_tokens=cached_resp.output_tokens,
                    cache_hit=True,
                )
                if isinstance(cached_resp.output, CIOSynthesisResponse):
                    return cached_resp.output.synthesis
                data = cached_resp.output if isinstance(cached_resp.output, dict) else cached_resp.output.model_dump()
                inner = data.get("synthesis", data)
                return CIOSynthesis.model_validate(inner)

        req = LLMRequest(
            prompt=prompt_text,
            model="mock-cio-synthesis-v1",
            temperature=_CIO_MODEL_CONFIG["temperature"],
            max_tokens=_CIO_MODEL_CONFIG["max_tokens"],
            system_instruction=CIO_SYNTHESIS_SYSTEM_INSTRUCTION,
        )

        response: LLMResponse[Any] = self.provider.generate_structured(req, CIOSynthesisResponse)

        self.cost_tracker.record_call(
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_hit=False,
        )

        if self.cache is not None:
            self.cache.set(cache_key, response)

        if isinstance(response.output, CIOSynthesisResponse):
            return response.output.synthesis

        data = response.output if isinstance(response.output, dict) else response.output.model_dump()
        inner = data.get("synthesis", data)
        return CIOSynthesis.model_validate(inner)