"""Banking Business / Competitive Analyst Pipeline.

Specialist analyst for bank business quality, competitive positioning,
franchise strength, and growth drivers.
"""

from investiq.analysts.base_pipeline import BaseAnalystPipeline
from investiq.llm.base import LLMProvider
from investiq.llm.cache import LLMCache
from investiq.llm.cost import CostTracker
from investiq.models.analyst_input import AnalystInput
from investiq.prompts.banking_business_analyst import (
    BANKING_BUSINESS_SYSTEM_INSTRUCTION,
    PROMPT_VERSION,
    render_banking_business_analyst_prompt,
)


class BankingBusinessAnalyst(BaseAnalystPipeline):
    """Banking Business / Competitive Analyst pipeline.

    Specializes in assessing bank business quality, competitive positioning,
    franchise strength, growth drivers, and competitive threats.

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
        """Render the banking business analyst prompt from the input payload."""
        return render_banking_business_analyst_prompt(analyst_input)

    @property
    def _model_name(self) -> str:
        return "mock-banking-business-analyst-v1"

    @property
    def _analyst_type(self) -> str:
        return "banking_business_analyst"

    @property
    def _system_instruction(self) -> str:
        return BANKING_BUSINESS_SYSTEM_INSTRUCTION

    @property
    def _prompt_version(self) -> str:
        return PROMPT_VERSION