"""Test the MODEL_CAPABILITIES aliases structure across all providers."""

from providers.dial import DIALModelProvider
from providers.gemini import GeminiModelProvider
from providers.openai import OpenAIModelProvider
from providers.xai import XAIModelProvider


class TestSupportedModelsAliases:
    """Test that all providers have correctly structured MODEL_CAPABILITIES with aliases."""

    def test_gemini_provider_aliases(self):
        """Test Gemini provider's alias structure."""
        provider = GeminiModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.MODEL_CAPABILITIES.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "flash" in provider.MODEL_CAPABILITIES["gemini-2.5-flash"].aliases
        assert "flash2.5" in provider.MODEL_CAPABILITIES["gemini-2.5-flash"].aliases
        assert "pro" in provider.MODEL_CAPABILITIES["gemini-3.1-pro-preview"].aliases
        assert "pro2.5" in provider.MODEL_CAPABILITIES["gemini-2.5-pro"].aliases
        assert "flashlite" in provider.MODEL_CAPABILITIES["gemini-3.1-flash-lite-preview"].aliases
        assert "flash-lite" in provider.MODEL_CAPABILITIES["gemini-3.1-flash-lite-preview"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("flash") == "gemini-2.5-flash"
        assert provider._resolve_model_name("flash2.5") == "gemini-2.5-flash"
        assert provider._resolve_model_name("pro") == "gemini-3.1-pro-preview"
        assert provider._resolve_model_name("pro2.5") == "gemini-2.5-pro"
        assert provider._resolve_model_name("flashlite") == "gemini-3.1-flash-lite-preview"

        # Test case insensitive resolution
        assert provider._resolve_model_name("Flash") == "gemini-2.5-flash"
        assert provider._resolve_model_name("PRO") == "gemini-3.1-pro-preview"

    def test_openai_provider_aliases(self):
        """Test OpenAI provider's alias structure."""
        provider = OpenAIModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.MODEL_CAPABILITIES.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "gpt" in provider.MODEL_CAPABILITIES["gpt-5.4-pro"].aliases
        assert "gptpro" in provider.MODEL_CAPABILITIES["gpt-5.4-pro"].aliases
        assert "gpt54" in provider.MODEL_CAPABILITIES["gpt-5.4"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("gpt") == "gpt-5.4-pro"
        assert provider._resolve_model_name("gptpro") == "gpt-5.4-pro"
        assert provider._resolve_model_name("gpt54") == "gpt-5.4"
        assert provider._resolve_model_name("gpt5.4") == "gpt-5.4"

        # Test case insensitive resolution
        assert provider._resolve_model_name("GPT") == "gpt-5.4-pro"
        assert provider._resolve_model_name("GPT54") == "gpt-5.4"

    def test_xai_provider_aliases(self):
        """Test XAI provider's alias structure."""
        provider = XAIModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.MODEL_CAPABILITIES.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "grok" in provider.MODEL_CAPABILITIES["grok-4.20-reasoning"].aliases
        assert "grok4" in provider.MODEL_CAPABILITIES["grok-4.20-reasoning"].aliases
        assert "grok-fast" in provider.MODEL_CAPABILITIES["grok-code-fast-1"].aliases
        assert "grok4fast" in provider.MODEL_CAPABILITIES["grok-code-fast-1"].aliases
        assert "grokcode" in provider.MODEL_CAPABILITIES["grok-code-fast-1"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("grok") == "grok-4.20-reasoning"
        assert provider._resolve_model_name("grok4") == "grok-4.20-reasoning"
        assert provider._resolve_model_name("grok-fast") == "grok-code-fast-1"
        assert provider._resolve_model_name("grok4fast") == "grok-code-fast-1"
        assert provider._resolve_model_name("grokcode") == "grok-code-fast-1"

        # Test case insensitive resolution
        assert provider._resolve_model_name("Grok") == "grok-4.20-reasoning"
        assert provider._resolve_model_name("GROK-FAST") == "grok-code-fast-1"

    def test_dial_provider_aliases(self):
        """Test DIAL provider's alias structure."""
        provider = DIALModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.MODEL_CAPABILITIES.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "sonnet-4.1" in provider.MODEL_CAPABILITIES["anthropic.claude-sonnet-4.1-20250805-v1:0"].aliases
        assert "opus-4.1" in provider.MODEL_CAPABILITIES["anthropic.claude-opus-4.1-20250805-v1:0"].aliases
        assert "gemini-2.5-pro" in provider.MODEL_CAPABILITIES["gemini-2.5-pro-preview-05-06"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("sonnet-4.1") == "anthropic.claude-sonnet-4.1-20250805-v1:0"
        assert provider._resolve_model_name("opus-4.1") == "anthropic.claude-opus-4.1-20250805-v1:0"

        # Test case insensitive resolution
        assert provider._resolve_model_name("SONNET-4.1") == "anthropic.claude-sonnet-4.1-20250805-v1:0"

    def test_list_models_includes_aliases(self):
        """Test that list_models returns both base models and aliases."""
        # Test Gemini
        gemini_provider = GeminiModelProvider("test-key")
        gemini_models = gemini_provider.list_models(respect_restrictions=False)
        assert "gemini-2.5-flash" in gemini_models
        assert "flash" in gemini_models
        assert "gemini-3.1-pro-preview" in gemini_models
        assert "pro" in gemini_models
        assert "gemini-2.5-pro" in gemini_models
        assert "pro2.5" in gemini_models

        # Test OpenAI
        openai_provider = OpenAIModelProvider("test-key")
        openai_models = openai_provider.list_models(respect_restrictions=False)
        assert "gpt-5.4-pro" in openai_models
        assert "gpt" in openai_models
        assert "gpt-5.4" in openai_models
        assert "gpt54" in openai_models

        # Test XAI
        xai_provider = XAIModelProvider("test-key")
        xai_models = xai_provider.list_models(respect_restrictions=False)
        assert "grok-4.20-reasoning" in xai_models
        assert "grok" in xai_models
        assert "grok-code-fast-1" in xai_models
        assert "grok-fast" in xai_models

        # Test DIAL
        dial_provider = DIALModelProvider("test-key")
        dial_models = dial_provider.list_models(respect_restrictions=False)
        assert "anthropic.claude-sonnet-4.1-20250805-v1:0" in dial_models
        assert "sonnet-4.1" in dial_models

    def test_list_models_all_known_variant_includes_aliases(self):
        """Unified list_models should support lowercase, alias-inclusive listings."""
        # Test Gemini
        gemini_provider = GeminiModelProvider("test-key")
        gemini_all = gemini_provider.list_models(
            respect_restrictions=False,
            include_aliases=True,
            lowercase=True,
            unique=True,
        )
        assert "gemini-2.5-flash" in gemini_all
        assert "flash" in gemini_all
        assert "gemini-2.5-pro" in gemini_all
        assert "pro" in gemini_all
        # All should be lowercase
        assert all(model == model.lower() for model in gemini_all)

        # Test OpenAI
        openai_provider = OpenAIModelProvider("test-key")
        openai_all = openai_provider.list_models(
            respect_restrictions=False,
            include_aliases=True,
            lowercase=True,
            unique=True,
        )
        assert "gpt-5.4-pro" in openai_all
        assert "gpt" in openai_all
        assert "gpt-5.4" in openai_all
        assert "gpt54" in openai_all
        # All should be lowercase
        assert all(model == model.lower() for model in openai_all)

    def test_no_string_shorthand_in_supported_models(self):
        """Test that no provider has string-based shorthands anymore."""
        providers = [
            GeminiModelProvider("test-key"),
            OpenAIModelProvider("test-key"),
            XAIModelProvider("test-key"),
            DIALModelProvider("test-key"),
        ]

        for provider in providers:
            for model_name, config in provider.MODEL_CAPABILITIES.items():
                # All values must be ModelCapabilities objects, not strings or dicts
                from providers.shared import ModelCapabilities

                assert isinstance(config, ModelCapabilities), (
                    f"{provider.__class__.__name__}.MODEL_CAPABILITIES['{model_name}'] "
                    f"must be a ModelCapabilities object, not {type(config).__name__}"
                )

    def test_resolve_returns_original_if_not_found(self):
        """Test that _resolve_model_name returns original name if alias not found."""
        providers = [
            GeminiModelProvider("test-key"),
            OpenAIModelProvider("test-key"),
            XAIModelProvider("test-key"),
            DIALModelProvider("test-key"),
        ]

        for provider in providers:
            # Test with unknown model name
            assert provider._resolve_model_name("unknown-model") == "unknown-model"
            assert provider._resolve_model_name("gpt-4") == "gpt-4"
            assert provider._resolve_model_name("claude-4") == "claude-4"
