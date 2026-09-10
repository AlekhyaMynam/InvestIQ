"""Unit tests for GeminiProvider using mocked SDK responses.

Ensures ZERO real network calls are made during tests and verifies secret protection,
structured parsing, token extraction, error handling, and cost guard enforcement.
"""

from unittest.mock import MagicMock, patch

import pytest

from investiq.config import ConfigurationError
from investiq.llm.base import CostGuardError, LLMRequest
from investiq.llm.gemini import GeminiProvider
from investiq.models.research import FindingCategory, ResearchFinding, ResearchFindingResponse


class TestGeminiProviderConstructionAndGuard:
    """Test GeminiProvider construction, configuration validation, and cost guard enforcement."""

    def test_construction_blocked_in_offline_mode(self, monkeypatch):
        """Constructing GeminiProvider when INVESTIQ_ALLOW_REAL_LLM is False raises CostGuardError."""
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "false")
        monkeypatch.setenv("GEMINI_API_KEY", "dummy_key")

        with pytest.raises(CostGuardError, match="OFFLINE mode"):
            GeminiProvider()

    def test_construction_requires_api_key(self, monkeypatch):
        """Constructing GeminiProvider with allow_real=True but missing key raises ConfigurationError."""
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "true")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with pytest.raises(ConfigurationError, match="requires a valid GEMINI_API_KEY"):
            GeminiProvider()

    def test_successful_construction_with_mocked_client(self, monkeypatch):
        """With allow_real=True and API key set, GeminiProvider constructs safely with mocked Client."""
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "true")
        monkeypatch.setenv("GEMINI_API_KEY", "test_secret_key_123")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")

        with patch("google.genai.Client") as mock_client_cls:
            provider = GeminiProvider()
            assert provider.model == "gemini-1.5-pro"
            assert mock_client_cls.called

    def test_secret_protection_in_repr(self, monkeypatch):
        """API key is masked in provider repr()."""
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "true")
        monkeypatch.setenv("GEMINI_API_KEY", "secret_key_xyz987")

        with patch("google.genai.Client"):
            provider = GeminiProvider()
            repr_str = repr(provider)
            assert "secret_key_xyz987" not in repr_str
            assert "***" in repr_str


class TestGeminiProviderGeneration:
    """Test structured content generation with mocked SDK responses."""

    @pytest.fixture
    def mock_gemini_provider(self, monkeypatch):
        monkeypatch.setenv("INVESTIQ_ALLOW_REAL_LLM", "true")
        monkeypatch.setenv("GEMINI_API_KEY", "secret_key_999")

        with patch("google.genai.Client") as mock_client_cls:
            provider = GeminiProvider()
            provider.client = mock_client_cls.return_value
            return provider

    def test_generate_structured_success(self, mock_gemini_provider):
        """Test formatting request and parsing valid JSON structured response."""
        # Setup mock SDK response
        mock_response = MagicMock()
        mock_response.text = '''[
            {
                "analyst": "financial_analyst",
                "title": "Strong Liquidity",
                "statement": "High CASA ratio.",
                "confidence": 0.85,
                "evidence_ids": ["SYN-001"],
                "category": "liability_franchise"
            }
        ]'''
        mock_response.usage_metadata.prompt_token_count = 150
        mock_response.usage_metadata.candidates_token_count = 60

        mock_gemini_provider.client.models.generate_content.return_value = mock_response

        req = LLMRequest(prompt="Analyze HDFC Bank", model="gemini-1.5-pro")
        resp = mock_gemini_provider.generate_structured(req, list)

        assert resp.model == "gemini-1.5-pro"
        assert resp.input_tokens == 150
        assert resp.output_tokens == 60
        assert resp.estimated_cost > 0.0
        assert resp.cache_hit is False
        assert len(resp.output) == 1
        assert resp.output[0]["title"] == "Strong Liquidity"

    def test_token_usage_and_cost_metadata(self, mock_gemini_provider):
        """Token counts and cost calculations match expected formula."""
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_response.usage_metadata.prompt_token_count = 1_000_000  # $3.50
        mock_response.usage_metadata.candidates_token_count = 1_000_000  # $10.50

        mock_gemini_provider.client.models.generate_content.return_value = mock_response

        req = LLMRequest(prompt="Test token count", model="gemini-1.5-pro")
        resp = mock_gemini_provider.generate_structured(req, list)

        assert resp.input_tokens == 1_000_000
        assert resp.output_tokens == 1_000_000
        assert resp.estimated_cost == pytest.approx(14.00)

    def test_malformed_json_response_handling(self, mock_gemini_provider):
        """Malformed non-JSON response raises clean error with masked secrets."""
        mock_response = MagicMock()
        mock_response.text = "This is not JSON text from model!"

        mock_gemini_provider.client.models.generate_content.return_value = mock_response

        req = LLMRequest(prompt="Test malformed JSON")
        with pytest.raises(RuntimeError, match="Failed to parse Gemini structured JSON output"):
            mock_gemini_provider.generate_structured(req, list)

    def test_api_network_error_handling_and_secret_masking(self, mock_gemini_provider):
        """SDK exception containing API key is masked before being re-raised."""
        # Simulate SDK raising exception that includes the raw API key
        mock_gemini_provider.client.models.generate_content.side_effect = Exception(
            "API failure on endpoint with key secret_key_999"
        )

        req = LLMRequest(prompt="Test API error")
        with pytest.raises(RuntimeError) as exc_info:
            mock_gemini_provider.generate_structured(req, list)

        err_str = str(exc_info.value)
        assert "secret_key_999" not in err_str
        assert "***" in err_str

    def test_pydantic_schema_passed_to_sdk_config(self, mock_gemini_provider):
        """ResearchFindingResponse should produce non-null response_schema in SDK config."""
        mock_response = MagicMock()
        mock_response.text = '{"findings": [{"analyst": "financial_analyst", "title": "Test", "statement": "Test", "confidence": 0.5, "evidence_ids": ["SYN-001"], "category": "liability_franchise"}]}'
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 10

        mock_gemini_provider.client.models.generate_content.return_value = mock_response

        req = LLMRequest(prompt="Test", model="gemini-1.5-pro")
        resp = mock_gemini_provider.generate_structured(req, ResearchFindingResponse)

        # Verify that generate_content was called with a config that has response_schema set
        call_kwargs = mock_gemini_provider.client.models.generate_content.call_args[1]
        config = call_kwargs.get("config")
        assert config is not None
        assert config.response_schema is not None
        assert hasattr(config.response_schema, "model_json_schema")

        # Verify output is properly parsed as ResearchFindingResponse
        assert isinstance(resp.output, ResearchFindingResponse)
        assert len(resp.output.findings) == 1
        assert resp.output.findings[0].analyst == "financial_analyst"

    def test_call_budget_limit_guard(self, mock_gemini_provider, monkeypatch):
        """Exceeding MAX_EXTERNAL_LLM_CALLS raises CostGuardError."""
        mock_gemini_provider.settings.max_external_llm_calls = 1
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_gemini_provider.client.models.generate_content.return_value = mock_response

        req = LLMRequest(prompt="Call 1")
        mock_gemini_provider.generate_structured(req, list)

        # Call 2 should exceed budget limit of 1
        req2 = LLMRequest(prompt="Call 2")
        with pytest.raises(CostGuardError, match="External LLM call limit reached"):
            mock_gemini_provider.generate_structured(req2, list)
