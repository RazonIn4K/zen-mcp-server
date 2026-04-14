"""Tests for X.AI provider implementation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.shared import ProviderType
from providers.xai import XAIModelProvider


class TestXAIProvider:
    """Test X.AI provider functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear restriction service cache before each test
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        # Clear restriction service cache after each test
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @patch.dict(os.environ, {"XAI_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = XAIModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.XAI
        assert provider.base_url == "https://api.x.ai/v1"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = XAIModelProvider("test-key", base_url="https://custom.x.ai/v1")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.x.ai/v1"

    def test_model_validation(self):
        """Test model name validation."""
        provider = XAIModelProvider("test-key")

        # Test valid models
        assert provider.validate_model_name("grok") is True
        assert provider.validate_model_name("grok4") is True
        assert provider.validate_model_name("grok-4") is True
        assert provider.validate_model_name("grok-4.20-reasoning") is True
        assert provider.validate_model_name("grok-fast") is True
        assert provider.validate_model_name("grok4fast") is True
        assert provider.validate_model_name("grok-code-fast-1") is True
        assert provider.validate_model_name("grokcode") is True

        # Deprecated aliases/models should not validate
        assert provider.validate_model_name("grok-3") is False
        assert provider.validate_model_name("grok-3-fast") is False
        assert provider.validate_model_name("grok3") is False
        assert provider.validate_model_name("grokfast") is False

        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("gemini-pro") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = XAIModelProvider("test-key")

        # Test shorthand resolution
        assert provider._resolve_model_name("grok") == "grok-4.20-reasoning"
        assert provider._resolve_model_name("grok4") == "grok-4.20-reasoning"
        assert provider._resolve_model_name("grok-4") == "grok-4.20-reasoning"
        assert provider._resolve_model_name("grok-fast") == "grok-code-fast-1"
        assert provider._resolve_model_name("grok4fast") == "grok-code-fast-1"
        assert provider._resolve_model_name("grokcode") == "grok-code-fast-1"

        # Test full name passthrough
        assert provider._resolve_model_name("grok-4.20-reasoning") == "grok-4.20-reasoning"
        assert provider._resolve_model_name("grok-code-fast-1") == "grok-code-fast-1"

    def test_get_capabilities_grok_reasoning(self):
        """Test getting model capabilities for Grok 4.20 reasoning."""
        provider = XAIModelProvider("test-key")

        capabilities = provider.get_capabilities("grok-4.20-reasoning")
        assert capabilities.model_name == "grok-4.20-reasoning"
        assert capabilities.friendly_name == "X.AI (Grok 4.20 Reasoning)"
        assert capabilities.context_window == 2_000_000
        assert capabilities.provider == ProviderType.XAI
        assert capabilities.supports_extended_thinking
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_json_mode is True
        assert capabilities.supports_images is True

        # Test temperature range
        assert capabilities.temperature_constraint.min_temp == 0.0
        assert capabilities.temperature_constraint.max_temp == 2.0
        assert capabilities.temperature_constraint.default_temp == 0.3

    def test_get_capabilities_grok_code_fast(self):
        """Test getting model capabilities for Grok Code Fast."""
        provider = XAIModelProvider("test-key")

        capabilities = provider.get_capabilities("grok-code-fast-1")
        assert capabilities.model_name == "grok-code-fast-1"
        assert capabilities.friendly_name == "X.AI (Grok Code Fast)"
        assert capabilities.context_window == 256_000
        assert capabilities.provider == ProviderType.XAI
        assert capabilities.supports_extended_thinking is False
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_json_mode is True
        assert capabilities.supports_images is False

        # Test temperature range
        assert capabilities.temperature_constraint.min_temp == 0.0
        assert capabilities.temperature_constraint.max_temp == 2.0
        assert capabilities.temperature_constraint.default_temp == 0.3

    def test_get_capabilities_grok3_fast(self):
        """Test getting model capabilities for GROK-3 Fast."""
        provider = XAIModelProvider("test-key")

        capabilities = provider.get_capabilities("grok-code-fast-1")
        assert capabilities.model_name == "grok-code-fast-1"
        assert capabilities.friendly_name == "X.AI (Grok Code Fast)"
        assert capabilities.context_window == 256_000
        assert capabilities.provider == ProviderType.XAI
        assert not capabilities.supports_extended_thinking

    def test_get_capabilities_with_shorthand(self):
        """Test getting model capabilities with shorthand."""
        provider = XAIModelProvider("test-key")

        capabilities = provider.get_capabilities("grok")
        assert capabilities.model_name == "grok-4.20-reasoning"  # Should resolve to full name
        assert capabilities.context_window == 2_000_000

        capabilities_fast = provider.get_capabilities("grok-fast")
        assert capabilities_fast.model_name == "grok-code-fast-1"  # Should resolve to full name

    def test_unsupported_model_capabilities(self):
        """Test error handling for unsupported models."""
        provider = XAIModelProvider("test-key")

        with pytest.raises(ValueError, match="Unsupported model 'invalid-model' for provider xai"):
            provider.get_capabilities("invalid-model")

    def test_extended_thinking_flags(self):
        """X.AI capabilities should expose extended thinking support correctly."""
        provider = XAIModelProvider("test-key")

        thinking_aliases = ["grok-4", "grok", "grok4"]
        for alias in thinking_aliases:
            assert provider.get_capabilities(alias).supports_extended_thinking is True

        non_thinking_aliases = ["grok-fast", "grok4fast", "grok-code-fast-1", "grokcode"]
        for alias in non_thinking_aliases:
            assert provider.get_capabilities(alias).supports_extended_thinking is False

    def test_provider_type(self):
        """Test provider type identification."""
        provider = XAIModelProvider("test-key")
        assert provider.get_provider_type() == ProviderType.XAI

    @patch.dict(os.environ, {"XAI_ALLOWED_MODELS": "grok-fast"})
    def test_model_restrictions(self):
        """Test model restrictions functionality."""
        # Clear cached restriction service
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = XAIModelProvider("test-key")

        # grok-fast should be allowed
        assert provider.validate_model_name("grok-fast") is True
        assert provider.validate_model_name("grok4fast") is True  # Shorthand alias
        assert provider.validate_model_name("grok-code-fast-1") is True

        # grok should be blocked (resolves to grok-4.20-reasoning which is not allowed)
        assert provider.validate_model_name("grok") is False

    @patch.dict(os.environ, {"XAI_ALLOWED_MODELS": "grok,grok-code"})
    def test_multiple_model_restrictions(self):
        """Test multiple models in restrictions."""
        # Clear cached restriction service
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = XAIModelProvider("test-key")

        # Shorthand "grok" should be allowed (resolves to grok-4.20-reasoning)
        assert provider.validate_model_name("grok") is True

        # Full name should be allowed as well
        assert provider.validate_model_name("grok-4.20-reasoning") is True

        # grok-code aliases should be allowed
        assert provider.validate_model_name("grok-code") is True
        assert provider.validate_model_name("grokcode") is True
        assert provider.validate_model_name("grok-code-fast-1") is True

        # grok-fast resolves to the same code model and should be allowed
        assert provider.validate_model_name("grok-fast") is True

    @patch.dict(os.environ, {"XAI_ALLOWED_MODELS": "grok,grok-4.20-reasoning,grok-fast"})
    def test_both_shorthand_and_full_name_allowed(self):
        """Test that both shorthand and full name can be allowed."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = XAIModelProvider("test-key")

        # Both shorthand and full name should be allowed
        assert provider.validate_model_name("grok") is True  # Resolves to grok-4.20-reasoning
        assert provider.validate_model_name("grok-4.20-reasoning") is True
        assert provider.validate_model_name("grok-fast") is True
        assert provider.validate_model_name("grok-code-fast-1") is True

    @patch.dict(os.environ, {"XAI_ALLOWED_MODELS": ""})
    def test_empty_restrictions_allows_all(self):
        """Test that empty restrictions allow all models."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = XAIModelProvider("test-key")

        assert provider.validate_model_name("grok-4.20-reasoning") is True
        assert provider.validate_model_name("grok-code-fast-1") is True
        assert provider.validate_model_name("grok") is True
        assert provider.validate_model_name("grok4") is True
        assert provider.validate_model_name("grok-fast") is True
        assert provider.validate_model_name("grokcode") is True

    def test_friendly_name(self):
        """Test friendly name constant."""
        provider = XAIModelProvider("test-key")
        assert provider.FRIENDLY_NAME == "X.AI"

        capabilities = provider.get_capabilities("grok")
        assert capabilities.friendly_name == "X.AI (Grok 4.20 Reasoning)"

    def test_supported_models_structure(self):
        """Test that MODEL_CAPABILITIES has the correct structure."""
        provider = XAIModelProvider("test-key")

        # Check that all expected base models are present
        assert "grok-4.20-reasoning" in provider.MODEL_CAPABILITIES
        assert "grok-code-fast-1" in provider.MODEL_CAPABILITIES

        # Check model configs have required fields
        from providers.shared import ModelCapabilities

        grok4_config = provider.MODEL_CAPABILITIES["grok-4.20-reasoning"]
        assert isinstance(grok4_config, ModelCapabilities)
        assert hasattr(grok4_config, "context_window")
        assert hasattr(grok4_config, "supports_extended_thinking")
        assert hasattr(grok4_config, "aliases")
        assert grok4_config.context_window == 2_000_000
        assert grok4_config.supports_extended_thinking is True

        # Check aliases are correctly structured
        assert "grok" in grok4_config.aliases
        assert "grok-4" in grok4_config.aliases
        assert "grok4" in grok4_config.aliases

        grok_fast_config = provider.MODEL_CAPABILITIES["grok-code-fast-1"]
        assert grok_fast_config.context_window == 256_000
        assert grok_fast_config.supports_extended_thinking is False
        assert "grok-fast" in grok_fast_config.aliases
        assert "grok4fast" in grok_fast_config.aliases

        grok_code_config = provider.MODEL_CAPABILITIES["grok-code-fast-1"]
        assert grok_code_config.context_window == 256_000
        assert grok_code_config.supports_extended_thinking is False
        assert "grokcode" in grok_code_config.aliases

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content resolves aliases before making API calls.

        This is the CRITICAL test that ensures aliases like 'grok' get resolved
        to 'grok-4' before being sent to X.AI API.
        """
        # Set up mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock the completion response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "grok-4.20-reasoning"  # API returns the resolved model name
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIModelProvider("test-key")

        # Call generate_content with alias 'grok'
        result = provider.generate_content(
            prompt="Test prompt", model_name="grok", temperature=0.7  # This should be resolved to "grok-4"
        )

        # Verify the API was called with the RESOLVED model name
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # CRITICAL ASSERTION: The API should receive "grok-4", not "grok"
        assert (
            call_kwargs["model"] == "grok-4.20-reasoning"
        ), f"Expected 'grok-4.20-reasoning' but API received '{call_kwargs['model']}'"

        # Verify other parameters
        assert call_kwargs["temperature"] == 0.7
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "Test prompt"

        # Verify response
        assert result.content == "Test response"
        assert result.model_name == "grok-4.20-reasoning"  # Should be the resolved name

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_other_aliases(self, mock_openai_class):
        """Test other alias resolutions in generate_content."""
        from unittest.mock import MagicMock

        # Set up mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIModelProvider("test-key")

        # Test grok4 -> grok-4.20-reasoning
        mock_response.model = "grok-4.20-reasoning"
        provider.generate_content(prompt="Test", model_name="grok4", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-4.20-reasoning"

        # Test grok-4 -> grok-4.20-reasoning
        provider.generate_content(prompt="Test", model_name="grok-4", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-4.20-reasoning"

        # Test grok-fast -> grok-code-fast-1
        mock_response.model = "grok-code-fast-1"
        provider.generate_content(prompt="Test", model_name="grok-fast", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-code-fast-1"

        # Test grok4fast -> grok-code-fast-1
        provider.generate_content(prompt="Test", model_name="grok4fast", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-code-fast-1"

        # Test grokcode -> grok-code-fast-1
        mock_response.model = "grok-code-fast-1"
        provider.generate_content(prompt="Test", model_name="grokcode", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-code-fast-1"
