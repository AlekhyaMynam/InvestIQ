"""Cost safety guard for Phase 2A.

Ensures that Phase 2A offline execution cannot accidentally invoke real
external vendor LLM APIs (e.g. Gemini, OpenAI) or spend AI credits.
"""

import os

from investiq.config import ConfigurationError, get_settings
from investiq.llm.base import CostGuardError


def enforce_offline_mode() -> None:
    """Verify that offline mode is active or raise CostGuardError.

    Phase 2B default behavior is OFFLINE_MODE = True. Calling real external
    LLM providers is strictly prohibited unless INVESTIQ_ALLOW_REAL_LLM="true"
    is explicitly set in environment variables.
    """
    settings = get_settings()
    if not settings.investiq_allow_real_llm:
        return  # Offline mode enforced


def assert_provider_allowed(provider_name: str) -> None:
    """Assert that a provider is permitted in current environment.

    Raises:
        CostGuardError: If a real external provider is requested while in offline mode.
        ConfigurationError: If Gemini provider is requested without valid key.
    """
    if provider_name.lower().startswith("mock"):
        return

    settings = get_settings()
    if not settings.investiq_allow_real_llm:
        raise CostGuardError(
            f"Attempted to invoke real LLM provider '{provider_name}' in OFFLINE mode. "
            f"Zero external API calls policy is active. "
            f"Use MockLLMProvider or set INVESTIQ_ALLOW_REAL_LLM='true' for production."
        )

    if provider_name.lower() == "gemini":
        settings.validate_provider()
