"""Google AI Studio Gemini LLM Provider implementation.

Implements the LLMProvider interface using the official `google-genai` SDK.
Enforces cost safety controls, secret protection, token tracking, and structured JSON output.

DO NOT make real API calls in testing or offline mode.
"""

import json
import re
import time
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter

from investiq.config import ConfigurationError, get_settings
from investiq.llm.base import LLMProvider, LLMRequest, LLMResponse
from investiq.llm.cost import DEFAULT_PRICING_REGISTRY, ModelPricing
from investiq.llm.guard import assert_provider_allowed


T = TypeVar("T", bound=BaseModel)


class GeminiProvider(LLMProvider):
    """LLM Provider implementation for Google Gemini via google-genai SDK.

    Attributes:
        client: google.genai.Client instance (initialized lazily or mocked).
        settings: Application settings from config.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialize GeminiProvider.

        Validates offline mode safety and configuration. Does not hardcode keys or models.
        """
        assert_provider_allowed("gemini")

        self.settings = get_settings()
        # Override settings if explicitly passed (and not None)
        effective_key = api_key or self.settings.gemini_api_key
        effective_model = model or self.settings.gemini_model

        # Perform provider validation
        if not self.settings.investiq_allow_real_llm:
            from investiq.llm.base import CostGuardError
            raise CostGuardError(
                "GeminiProvider requested but INVESTIQ_ALLOW_REAL_LLM is false. "
                "Zero external API calls policy is active."
            )

        if not effective_key or not effective_key.strip():
            raise ConfigurationError(
                "GeminiProvider requires a valid GEMINI_API_KEY. Key is missing or empty."
            )

        self.api_key = effective_key
        self.model = effective_model
        self._external_calls_count = 0

        # Lazy import of google.genai client
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            self._raise_safe_exception(e, "Failed to initialize Gemini Client")

    def _mask_secrets(self, text: str) -> str:
        """Scrub any occurrence of the API key from a string."""
        if hasattr(self, "api_key") and self.api_key:
            return text.replace(self.api_key, "***")
        return text

    def _raise_safe_exception(self, original_exc: Exception, context_msg: str) -> None:
        """Sanitize exception message to ensure no secret API keys leak into logs/tracebacks."""
        clean_msg = self._mask_secrets(str(original_exc))
        safe_exc_msg = f"{context_msg}: {clean_msg}"
        if isinstance(original_exc, ConfigurationError):
            raise ConfigurationError(safe_exc_msg)
        raise RuntimeError(safe_exc_msg) from None

    def __repr__(self) -> str:
        """Return safe string representation omitting secret key."""
        return f"GeminiProvider(model='{self.model}', api_key=***)"

    def generate_structured(
        self,
        request: LLMRequest,
        response_schema: type[T],
    ) -> LLMResponse[T]:
        """Generate structured output validated against a Pydantic schema using Gemini SDK."""
        assert_provider_allowed("gemini")

        # Check call budget limit
        if (
            self.settings.max_external_llm_calls > 0
            and self._external_calls_count >= self.settings.max_external_llm_calls
        ):
            from investiq.llm.base import CostGuardError
            raise CostGuardError(
                f"External LLM call limit reached ({self.settings.max_external_llm_calls} calls max)."
            )

        # If the request carries a mock model identifier (analyst/CIO), substitute
        # the production Gemini model configured for this provider. This prevents
        # Gemini API from receiving unsupported model identifiers.
        if request.model.startswith("mock-"):
            target_model = self.model
        else:
            target_model = request.model

        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
            system_instruction=request.system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema if hasattr(response_schema, "model_json_schema") else None,
        )

        start_time = time.perf_counter()

        try:
            raw_response = self.client.models.generate_content(
                model=target_model,
                contents=request.prompt,
                config=config,
            )
            self._external_calls_count += 1
        except Exception as e:
            self._raise_safe_exception(e, "Gemini API call failed")

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Extract raw text response
        response_text = getattr(raw_response, "text", "") or ""

        # Extract usage metadata
        usage_meta = getattr(raw_response, "usage_metadata", None)
        input_tokens = getattr(usage_meta, "prompt_token_count", 0) if usage_meta else 0
        output_tokens = getattr(usage_meta, "candidates_token_count", 0) if usage_meta else 0

        # Calculate estimated cost
        pricing = DEFAULT_PRICING_REGISTRY.get(
            target_model, ModelPricing(model_id=target_model, input_price_per_1m=0.30, output_price_per_1m=2.50)
        )
        estimated_cost = pricing.calculate_cost(input_tokens, output_tokens)

        # Parse structured JSON output matching response_schema
        try:
            if hasattr(response_schema, "model_validate_json"):
                parsed_output = response_schema.model_validate_json(response_text)
            else:
                adapter = TypeAdapter(response_schema)
                parsed_output = adapter.validate_json(response_text)
        except Exception as e:
            self._raise_safe_exception(
                e, f"Failed to parse Gemini structured JSON output into schema {response_schema}"
            )

        return LLMResponse[T](
            output=parsed_output,
            raw_text=self._mask_secrets(response_text),
            model=target_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(elapsed_ms, 2),
            cache_hit=False,
            estimated_cost=estimated_cost,
        )
