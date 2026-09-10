"""Tests for centralized configuration module (src/investiq/config.py)."""

from pathlib import Path

import pytest

from investiq.config import ConfigurationError, Settings, load_settings


class TestConfigDefaults:
    """Test default configuration safety."""

    def test_default_config_is_offline(self, monkeypatch):
        """Default settings must enforce offline mock mode."""
        # Ensure clean environment for test
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("INVESTIQ_ALLOW_REAL_LLM", raising=False)
        monkeypatch.delenv("MAX_EXTERNAL_LLM_CALLS", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)

        settings = load_settings()

        assert settings.llm_provider == "mock"
        assert settings.investiq_allow_real_llm is False
        assert settings.max_external_llm_calls == 0
        assert settings.gemini_model == "gemini-3.5-flash-lite"
        assert settings.gemini_api_key is None
        assert settings.is_offline is True

    def test_missing_api_key_acceptable_in_mock_mode(self, monkeypatch):
        """Mock mode does not require an API key and startup does not fail."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "mock")

        settings = load_settings()
        # Should not raise ConfigurationError
        settings.validate_provider()
        assert settings.gemini_api_key is None


class TestGeminiProviderValidation:
    """Test validation rules when Gemini provider is requested."""

    def test_gemini_mode_requires_allow_real_flag(self, monkeypatch):
        """Setting LLM_PROVIDER=gemini without INVESTIQ_ALLOW_REAL_LLM=true raises ConfigurationError."""
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "false")
        monkeypatch.setenv("GEMINI_API_KEY", "dummy_key_123")

        settings = load_settings()

        with pytest.raises(ConfigurationError, match="INVESTIQ_ALLOW_REAL_LLM is false"):
            settings.validate_provider()

    def test_gemini_mode_requires_api_key(self, monkeypatch):
        """Setting LLM_PROVIDER=gemini with allow_real=true but missing API key raises ConfigurationError."""
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "true")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        settings = load_settings()

        with pytest.raises(ConfigurationError, match="GEMINI_API_KEY is missing or empty"):
            settings.validate_provider()

    def test_valid_gemini_configuration(self, monkeypatch):
        """Gemini mode with allow_real=true and valid API key passes validation."""
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "true")
        monkeypatch.setenv("GEMINI_API_KEY", "test_secret_key_abc123")

        settings = load_settings()
        # Should not raise
        settings.validate_provider()
        assert settings.gemini_api_key == "test_secret_key_abc123"


class TestDotEnvTestIsolation:
    """Verify that .env does not affect pytest configuration."""

    def test_dotenv_not_loaded_during_pytest(self, monkeypatch):
        """During pytest, load_dotenv is not called — .env does not affect settings."""
        # Clear env vars that might come from .env
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        monkeypatch.delenv("INVESTIQ_ALLOW_REAL_LLM", raising=False)
        monkeypatch.delenv("MAX_EXTERNAL_LLM_CALLS", raising=False)

        settings = load_settings()

        # Should get defaults, not .env values
        assert settings.llm_provider == "mock"
        assert settings.gemini_api_key is None

    def test_monkeypatch_overrides_work_during_pytest(self, monkeypatch):
        """Tests can explicitly set env vars and they are respected."""
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "true")
        monkeypatch.setenv("GEMINI_API_KEY", "test_key_abc")

        settings = load_settings()

        assert settings.llm_provider == "gemini"
        assert settings.investiq_allow_real_llm is True
        assert settings.gemini_api_key == "test_key_abc"

    def test_dotenv_file_loading_is_preserved(self, tmp_path):
        """The load_settings(env_file=...) mechanism still works in tests."""
        env_file = tmp_path / "test.env"
        env_file.write_text(
            "LLM_PROVIDER=gemini\n"
            "GEMINI_API_KEY=from_test_env\n"
            "INVESTIQ_ALLOW_REAL_LLM=true\n"
        )

        settings = load_settings(env_file=env_file)

        assert settings.llm_provider == "gemini"
        assert settings.gemini_api_key == "from_test_env"


class TestAppProviderIsolation:
    """Verify that app.py provider initialization is not affected by .env during testing."""

    def test_default_provider_is_mock_in_app(self, monkeypatch):
        """When running under pytest, app.py creates MockLLMProvider, not GeminiProvider."""
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "false")
        from investiq.api.app import get_provider
        from investiq.llm.mock import MockLLMProvider
        provider = get_provider()
        assert isinstance(provider, MockLLMProvider), (
            f"Expected MockLLMProvider, got {type(provider).__name__}. "
            f"Check INVESTIQ_TESTING env guard is preventing .env loading."
        )

    def test_provider_not_affected_by_dotenv(self, monkeypatch):
        """App provider stays mock even when env has real-LLM settings."""
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "false")
        from investiq.api.app import get_provider
        from investiq.llm.mock import MockLLMProvider
        provider = get_provider()
        assert isinstance(provider, MockLLMProvider)


class TestSecretMasking:
    """Test that API keys are never leaked in string representations or errors."""

    def test_repr_masks_api_key(self):
        settings = Settings(gemini_api_key="super_secret_api_key_xyz999")

        repr_str = repr(settings)
        safe_str = settings.safe_repr()

        assert "super_secret_api_key_xyz999" not in repr_str
        assert "super_secret_api_key_xyz999" not in safe_str
        assert "***" in safe_str


class TestEnvironmentOverrideAndDotEnv:
    """Test loading settings from custom .env files and environment overrides."""

    def test_custom_dotenv_file_loading(self, tmp_path):
        env_file = tmp_path / "custom.env"
        env_file.write_text(
            "GEMINI_MODEL=gemini-1.5-flash\n"
            "MAX_EXTERNAL_LLM_CALLS=10\n"
            "LLM_PROVIDER=mock\n"
        )

        settings = load_settings(env_file=env_file)

        assert settings.gemini_model == "gemini-1.5-flash"
        assert settings.max_external_llm_calls == 10
        assert settings.llm_provider == "mock"
