"""Asset Quality Analyst Pipeline.

Specialist analyst for bank asset quality assessment — Gross NPA, Net NPA,
Credit Cost, and supported asset-quality trends.
"""

from investiq.analysts.base_pipeline import BaseAnalystPipeline
from investiq.llm.base import LLMProvider
from investiq.llm.cache import LLMCache
from investiq.llm.cost import CostTracker
from investiq.models.analyst_input import AnalystInput
from investiq.prompts.asset_quality_analyst import (
    ASSET_QUALITY_SYSTEM_INSTRUCTION,
    PROMPT_VERSION,
    render_asset_quality_analyst_prompt,
)


class AssetQualityAnalyst(BaseAnalystPipeline):
    """Asset Quality Analyst pipeline.

    Specializes in evaluating bank asset quality using Gross NPA, Net NPA,
    Credit Cost, and supported asset-quality trends.

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
        super().__init__(provider=provider, cache=cache, cost_tracker=cost_tracker)

    def _render_prompt(self, analyst_input: AnalystInput) -> str:
        """Render the asset quality analyst prompt from the input payload."""
        return render_asset_quality_analyst_prompt(analyst_input)

    @property
    def _model_name(self) -> str:
        return "mock-asset-quality-analyst-v1"

    @property
    def _analyst_type(self) -> str:
        return "asset_quality_analyst"

    @property
    def _system_instruction(self) -> str:
        return ASSET_QUALITY_SYSTEM_INSTRUCTION

    @property
    def _prompt_version(self) -> str:
        return PROMPT_VERSION