"""Mock LLM Provider for Phase 2A offline execution.

Makes ZERO network calls, costs $0 in API credits, and generates deterministic,
high-quality synthetic financial analyst findings for testing.
"""

import time
from typing import Any, TypeVar

from pydantic import BaseModel

from investiq.llm.base import LLMProvider, LLMRequest, LLMResponse
from investiq.llm.guard import assert_provider_allowed
from investiq.models.research import FindingCategory, ResearchFinding, ResearchFindingResponse
from investiq.models.synthesis import CIOSynthesis, CIOSynthesisResponse


T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider — deterministic, offline, zero-cost.

    Attributes:
        simulated_latency_ms: Artificial latency to simulate network call duration.
        preset_response: Optional override response object to return for custom test scenarios.
    """

    def __init__(
        self,
        simulated_latency_ms: float = 50.0,
        preset_response: BaseModel | list[BaseModel] | None = None,
    ) -> None:
        assert_provider_allowed("mock-financial-analyst-v1")
        self.simulated_latency_ms = simulated_latency_ms
        self.preset_response = preset_response

    @staticmethod
    def _pick_ids(valid_ids: list[str] | None, needed: int) -> list[str]:
        """Return up to `needed` evidence IDs from valid_ids, with empty fallback."""
        if valid_ids:
            return valid_ids[:needed]
        return []

    def generate_structured(
        self,
        request: LLMRequest,
        response_schema: type[T],
    ) -> LLMResponse[T]:
        """Generate structured output validated against response_schema without network calls."""
        assert_provider_allowed(request.model)

        start_time = time.perf_counter()

        # If custom preset response was injected, use it
        if self.preset_response is not None:
            output_obj = self.preset_response
        else:
            # Use provided evidence IDs from the request if available
            valid_ids = request.valid_evidence_ids or []
            # Generate default deterministic response matching requested schema
            output_obj = self._build_default_response(request, response_schema, valid_ids)

        # Estimate realistic token counts
        input_token_estimate = max(50, len(request.prompt) // 4)
        output_token_estimate = max(30, len(str(output_obj)) // 4)

        elapsed_ms = (time.perf_counter() - start_time) * 1000 + self.simulated_latency_ms

        return LLMResponse[T](
            output=output_obj,
            raw_text=str(output_obj),
            model=request.model,
            input_tokens=input_token_estimate,
            output_tokens=output_token_estimate,
            latency_ms=round(elapsed_ms, 2),
            cache_hit=False,
            estimated_cost=0.0,  # Mock provider costs $0.00
        )

    def _build_default_response(
        self,
        request: LLMRequest,
        response_schema: type[T],
        valid_ids: list[str] | None = None,
    ) -> Any:
        """Construct deterministic synthetic response data matching response_schema."""
        schema_name = getattr(response_schema, "__name__", str(response_schema))

        # If CIOSynthesisResponse schema requested, return a deterministic synthesis
        if response_schema is CIOSynthesisResponse or schema_name == "CIOSynthesisResponse":
            return CIOSynthesisResponse(
                synthesis=CIOSynthesis(
                    executive_summary="HDFC Bank demonstrates strong fundamentals with a robust deposit franchise, controlled asset quality, and consistent profitability. The bank's CASA ratio of ~35% provides a durable competitive advantage.",
                    investment_thesis="HDFC Bank's industry-leading deposit franchise and prudent underwriting position it well for sustained growth, though margin compression and competitive pressures warrant monitoring.",
                    key_strengths=[
                        "Industry-leading CASA ratio (~35%) providing low-cost funding advantage",
                        "Controlled asset quality with Gross NPA below 1.5%",
                        "Consistent profitability with ROE in the 15-16% range",
                    ],
                    key_concerns=[
                        "Post-merger margin compression from rising term deposit costs",
                        "Increasing competition from fintech and NBFCs",
                        "Unsecured retail credit growth could elevate credit costs",
                    ],
                    growth_drivers=[
                        "Strong deposit franchise enabling consistent loan growth",
                        "Digital adoption driving operating efficiency",
                        "Cross-selling opportunities from extensive branch network",
                    ],
                    risks=[
                        "Macroeconomic slowdown impacting loan growth and asset quality",
                        "Regulatory changes affecting capital adequacy or lending norms",
                        "Intense competition compressing net interest margins",
                    ],
                    bull_case="Sustained CASA ratio above 35%, NIM stability near 3.5%, and controlled credit costs drive ROE expansion toward 18%, with fair value appreciation as the market re-rates the franchise.",
                    base_case="CASA ratio stabilizes around 33-35%, NIM moderates to ~3.3%, credit costs remain controlled, delivering steady ROE of ~15% with moderate upside to fair value.",
                    bear_case="CASA ratio declines below 30% due to competitive pressure, NIM contracts below 3.0%, and credit costs rise above 1.0%, compressing ROE below 13% and limiting valuation upside.",
                    thesis_breakers=[
                        "CASA ratio falling below 30%",
                        "Gross NPA ratio exceeding 2.5%",
                        "Sustained NIM compression below 3.0%",
                        "Credit costs surging above 1.2%",
                    ],
                    overall_assessment="Conviction",
                )
            )

        # If ResearchFindingResponse schema requested, return wrapped findings
        if response_schema is ResearchFindingResponse or schema_name == "ResearchFindingResponse":
            if request.model == "mock-banking-business-analyst-v1":
                return ResearchFindingResponse(
                    findings=[
                        ResearchFinding(
                            analyst="banking_business_analyst",
                            title="Strong CASA-Driven Deposit Franchise",
                            statement="HDFC Bank's CASA ratio of ~35% reflects a strong, low-cost deposit franchise that provides stable funding and competitive advantage.",
                            confidence=0.88,
                            evidence_ids=self._pick_ids(valid_ids, 2) or ["SYN-HDFCBANK-CASA-001", "SYN-HDFCBANK-NIM-001"],
                            category=FindingCategory.COMPETITIVE_POSITION,
                            fundamental_observation="CASA ratio stood at ~35.0% in FY2025 with NIM at ~3.5%.",
                            why_it_matters="A high CASA ratio provides a durable cost advantage over peers and insulates margins during rate cycles.",
                            positive_implication="Strong brand and branch network enable continued low-cost deposit mobilization.",
                            negative_implication="Increasing competition from fintech and NBFCs could gradually erode the CASA advantage.",
                            thesis_breaker="CASA ratio falling below 30% or sustained market share loss in deposits.",
                        ),
                    ]
                )
            if request.model == "mock-asset-quality-analyst-v1":
                return ResearchFindingResponse(
                    findings=[
                        ResearchFinding(
                            analyst="asset_quality_analyst",
                            title="Controlled Gross NPA & Net NPA Levels",
                            statement="Gross NPA ratio at ~1.23% and Net NPA ratio at ~0.4% indicate strong asset quality with minimal credit stress.",
                            confidence=0.89,
                            evidence_ids=self._pick_ids(valid_ids, 2) or ["SYN-HDFCBANK-NPA-001", "SYN-HDFCBANK-CC-001"],
                            category=FindingCategory.ASSET_QUALITY,
                            fundamental_observation="Gross NPA ratio remained at ~1.23% in FY2025 with Net NPA at ~0.4%.",
                            why_it_matters="Low NPA levels reduce provisioning burden and support net profitability.",
                            positive_implication="High provision coverage ratio provides buffer against unexpected credit losses.",
                            negative_implication="Unsecured retail credit growth could elevate NPA ratios if macro conditions deteriorate.",
                            thesis_breaker="Gross NPA ratio exceeding 2.5% would signal deterioration in underwriting standards.",
                        ),
                    ]
                )
            return ResearchFindingResponse(
                findings=[
                    ResearchFinding(
                        analyst="financial_analyst",
                        title="Robust Deposit Franchise & Stable NIM Profile",
                        statement="HDFC Bank maintains an industry-leading CASA ratio (35-40%) and resilient Net Interest Margin (3.5%), supporting strong core operating profitability.",
                        confidence=0.90,
                        evidence_ids=self._pick_ids(valid_ids, 2) or ["SYN-HDFCBANK-CASA-001", "SYN-HDFCBANK-NIM-001"],
                        category=FindingCategory.LIABILITY_FRANCHISE,
                        fundamental_observation="CASA ratio stood at ~35.0% with NIM at ~3.5% in FY2025.",
                        why_it_matters="Low-cost deposit structure insulates net interest income during high interest rate cycles.",
                        positive_implication="Protects core net interest income and maintains low cost of funds relative to peers.",
                        negative_implication="Cost of term deposits has risen post-merger, compressing short-term spreads.",
                        thesis_breaker="CASA ratio falling below 30.0% or NIM contracting below 3.0%.",
                    ),
                ]
            )

        # If list, list[ResearchFinding], or ResearchFinding schema requested (backward compat)
        if (
            response_schema is list
            or "list" in schema_name.lower()
            or "ResearchFinding" in schema_name
            or hasattr(response_schema, "__origin__")
        ):
            return [
                {
                    "analyst": "financial_analyst",
                    "title": "Robust Deposit Franchise & Stable NIM Profile",
                    "statement": "HDFC Bank maintains an industry-leading CASA ratio (35-40%) and resilient Net Interest Margin (3.5%), supporting strong core operating profitability.",
                    "confidence": 0.90,
                    "evidence_ids": self._pick_ids(valid_ids, 2) or ["SYN-HDFCBANK-CASA-001", "SYN-HDFCBANK-NIM-001"],
                    "category": "liability_franchise",
                    "fundamental_observation": "CASA ratio stood at ~35.0% with NIM at ~3.5% in FY2025.",
                    "why_it_matters": "Low-cost deposit structure insulates net interest income during high interest rate cycles.",
                    "positive_implication": "Protects core net interest income and maintains low cost of funds relative to peers.",
                    "negative_implication": "Cost of term deposits has risen post-merger, compressing short-term spreads.",
                    "thesis_breaker": "CASA ratio falling below 30.0% or NIM contracting below 3.0%.",
                },
            ]

        if hasattr(response_schema, "model_construct"):
            return response_schema.model_construct()

        return {}
