"""Financial/Banking Analyst Pipeline.

Specializes in fundamental business analysis of banking companies.
"""

from investiq.analysts.base_pipeline import BaseAnalystPipeline
from investiq.llm.base import LLMProvider
from investiq.llm.cache import LLMCache
from investiq.llm.cost import CostTracker
from investiq.models.analyst_input import AnalystInput
from investiq.prompts.financial_analyst import (
    FINANCIAL_ANALYST_SYSTEM_INSTRUCTION,
    PROMPT_VERSION,
    render_financial_analyst_prompt,
)


class FinancialAnalystPipeline(BaseAnalystPipeline):
    """Financial/Banking Analyst pipeline.

    Specializes in analyzing fundamental business metrics, asset quality,
    operating efficiency, and liability franchise.

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
        """Render the financial analyst prompt from the input payload."""
        return render_financial_analyst_prompt(analyst_input)

    @property
    def _model_name(self) -> str:
        return "mock-financial-analyst-v1"

    @property
    def _analyst_type(self) -> str:
        return "financial_analyst"

    @property
    def _system_instruction(self) -> str:
        return FINANCIAL_ANALYST_SYSTEM_INSTRUCTION

    @property
    def _prompt_version(self) -> str:
        return PROMPT_VERSION
