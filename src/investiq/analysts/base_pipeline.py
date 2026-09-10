"""BaseAnalystPipeline — shared execution lifecycle for all analysts.

Provides the common template-method pattern for analyst execution:
prompt rendering, cache lookup, LLM provider invocation, cost tracking,
response parsing, and finding validation.

Subclasses provide only the analyst-specific hooks.

Usage:
    class MyAnalyst(BaseAnalystPipeline):
        def _render_prompt(self, analyst_input: AnalystInput) -> str: ...
        @property
        def _model_name(self) -> str: ...
        @property
        def _analyst_type(self) -> str: ...
        @property
        def _system_instruction(self) -> str: ...
        @property
        def _prompt_version(self) -> str: ...
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from investiq.analysts.base import ResearchAnalyst
from investiq.llm.base import LLMProvider, LLMRequest, LLMResponse
from investiq.llm.cache import LLMCache, build_cache_key
from investiq.llm.cost import CostTracker
from investiq.models.analyst_input import AnalystInput
from investiq.models.research import ResearchFinding, ResearchFindingResponse
from investiq.research.validator import validate_analyst_findings


# Shared model configuration for all analysts.
_DEFAULT_MODEL_CONFIG = {"temperature": 0.2, "max_tokens": 700}


class BaseAnalystPipeline(ResearchAnalyst):
    """Shared execution lifecycle for all analyst pipelines.

    Provides the template-method run() that subclasses customize via
    abstract hooks.

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

    # ── Template method ─────────────────────────────────────────────

    def run(self, analyst_input: AnalystInput) -> list[ResearchFinding]:
        """Execute the common analyst lifecycle.

        Subclasses customize behavior through the abstract hooks below.

        Returns:
            Validated list of ResearchFinding instances.
        """
        # 1. Render versioned prompt
        prompt_text = self._render_prompt(analyst_input)

        # 2. Build cache key
        normalized_input = analyst_input.model_dump_json()
        cache_key = build_cache_key(
            ticker=analyst_input.company.ticker,
            analyst_type=self._analyst_type,
            normalized_input=normalized_input,
            prompt_version=self._prompt_version,
            model_config=_DEFAULT_MODEL_CONFIG,
        )

        # 3. Check cache
        if self.cache is not None:
            cached_resp = self.cache.get(cache_key)
            if cached_resp is not None:
                self.cost_tracker.record_call(
                    model=cached_resp.model,
                    input_tokens=cached_resp.input_tokens,
                    output_tokens=cached_resp.output_tokens,
                    cache_hit=True,
                )
                if isinstance(cached_resp.output, ResearchFindingResponse):
                    findings = cached_resp.output.findings
                else:
                    findings = [
                        ResearchFinding.model_validate(f) if isinstance(f, dict) else f
                        for f in cached_resp.output
                    ]
                return validate_analyst_findings(findings, analyst_input.evidence_items)

        # 4. Invoke LLM Provider
        req = LLMRequest(
            prompt=prompt_text,
            model=self._model_name,
            temperature=_DEFAULT_MODEL_CONFIG["temperature"],
            max_tokens=_DEFAULT_MODEL_CONFIG["max_tokens"],
            system_instruction=self._system_instruction,
            valid_evidence_ids=[ev.evidence_id for ev in analyst_input.evidence_items],
        )

        response: LLMResponse[Any] = self.provider.generate_structured(req, ResearchFindingResponse)

        # Record usage
        self.cost_tracker.record_call(
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_hit=False,
        )

        # 5. Store in cache if enabled
        if self.cache is not None:
            self.cache.set(cache_key, response)

        # 6. Parse and validate output
        if isinstance(response.output, ResearchFindingResponse):
            findings = response.output.findings
        else:
            findings = [
                ResearchFinding.model_validate(f) if isinstance(f, dict) else f
                for f in response.output
            ]

        return validate_analyst_findings(findings, analyst_input.evidence_items)

    # ── Abstract hooks ──────────────────────────────────────────────

    @abstractmethod
    def _render_prompt(self, analyst_input: AnalystInput) -> str:
        """Render the analyst-specific prompt from the input payload."""
        ...

    @property
    @abstractmethod
    def _model_name(self) -> str:
        """Model identifier string used in LLMRequest and cache key."""
        ...

    @property
    @abstractmethod
    def _analyst_type(self) -> str:
        """Analyst type string used in cache key construction."""
        ...

    @property
    @abstractmethod
    def _system_instruction(self) -> str:
        """System instruction string for the LLM request."""
        ...

    @property
    @abstractmethod
    def _prompt_version(self) -> str:
        """Prompt version string used in cache key construction."""
        ...