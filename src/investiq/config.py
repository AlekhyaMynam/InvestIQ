"""Centralized application configuration for InvestIQ.

Loads environment variables from .env files via python-dotenv and provides
safe, offline-first default settings. Never logs or prints sensitive API keys.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class ConfigurationError(ValueError):
    """Raised when configuration parameters are invalid or missing required keys."""

    pass


class Settings(BaseModel):
    """Centralized application settings.

    Safe defaults enforce offline mock mode and zero external API calls.
    """

    gemini_api_key: str | None = Field(default=None, repr=False)
    gemini_model: str = "gemini-3.5-flash-lite"
    llm_provider: str = "mock"
    max_external_llm_calls: int = 0
    investiq_allow_real_llm: bool = False

    # BigQuery persistence configuration
    gcp_project_id: str | None = Field(default=None, repr=False)
    bigquery_dataset: str = "investiq"
    bigquery_location: str = "asia-south1"

    @property
    def is_offline(self) -> bool:
        """Return True if application is running in offline/mock mode."""
        return (
            self.llm_provider.lower().startswith("mock")
            or not self.investiq_allow_real_llm
        )

    def validate_provider(self) -> None:
        """Validate provider configuration.

        Raises:
            ConfigurationError: If Gemini provider is requested without API key
                                or without explicit production authorization.
        """
        if self.llm_provider.lower() == "gemini":
            if not self.investiq_allow_real_llm:
                raise ConfigurationError(
                    "LLM_PROVIDER is set to 'gemini' but INVESTIQ_ALLOW_REAL_LLM is false. "
                    "Set INVESTIQ_ALLOW_REAL_LLM=true to enable production calls."
                )
            if not self.gemini_api_key or not self.gemini_api_key.strip():
                raise ConfigurationError(
                    "LLM_PROVIDER is set to 'gemini' but GEMINI_API_KEY is missing or empty. "
                    "Please set GEMINI_API_KEY in environment or .env file."
                )

    def safe_repr(self) -> str:
        """Return a string representation omitting secret API keys."""
        masked_key = "***" if self.gemini_api_key else "None"
        return (
            f"Settings(llm_provider='{self.llm_provider}', "
            f"gemini_model='{self.gemini_model}', "
            f"investiq_allow_real_llm={self.investiq_allow_real_llm}, "
            f"max_external_llm_calls={self.max_external_llm_calls}, "
            f"gemini_api_key={masked_key})"
        )


# Load .env file into environment on module import.
# This is skipped during pytest execution so that tests are not
# affected by the developer's local .env configuration.
# During tests, environment variables must be set explicitly via
# monkeypatch or os.environ.
# pytest sets INVESTIQ_TESTING in tests/conftest.py BEFORE any
# test module imports, guaranteeing the guard is active during
# module-level code execution (import time).
if "INVESTIQ_TESTING" not in os.environ and "PYTEST_CURRENT_TEST" not in os.environ:
    load_dotenv(override=False)


def load_settings(env_file: Path | str | None = None) -> Settings:
    """Load settings from environment variables and optional .env file.

    Args:
        env_file: Path to a specific .env file to load.

    Returns:
        Settings: Population of application configuration.
    """
    if env_file:
        load_dotenv(dotenv_path=env_file, override=True)

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip() or None
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    llm_provider = os.getenv("LLM_PROVIDER", "mock").strip()

    try:
        max_calls = int(os.getenv("MAX_EXTERNAL_LLM_CALLS", "0"))
    except ValueError:
        max_calls = 0

    allow_real = os.getenv("INVESTIQ_ALLOW_REAL_LLM", "false").lower() == "true"

    # BigQuery persistence configuration
    gcp_project_id = os.getenv("GCP_PROJECT_ID", "").strip() or None
    bigquery_dataset = os.getenv("BIGQUERY_DATASET", "investiq").strip()
    bigquery_location = os.getenv("BIGQUERY_LOCATION", "asia-south1").strip()

    return Settings(
        gemini_api_key=gemini_key,
        gemini_model=gemini_model,
        llm_provider=llm_provider,
        max_external_llm_calls=max_calls,
        investiq_allow_real_llm=allow_real,
        gcp_project_id=gcp_project_id,
        bigquery_dataset=bigquery_dataset,
        bigquery_location=bigquery_location,
    )


# Default accessor
get_settings = load_settings
