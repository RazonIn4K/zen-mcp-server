"""Tests for model restriction functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.gemini import GeminiModelProvider
from providers.openai import OpenAIModelProvider
from providers.shared import ProviderType
from utils.model_restrictions import ModelRestrictionService


class TestModelRestrictionService:
    """Test cases for ModelRestrictionService."""

    def test_no_restrictions_by_default(self):
        """Test that no restrictions exist when env vars are not set."""
        with patch.dict(os.environ, {}, clear=True):
            service = ModelRestrictionService()

            # Should allow all models
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4")
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-pro")
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-flash")
            assert service.is_allowed(ProviderType.OPENROUTER, "anthropic/claude-opus-4.6")
            assert service.is_allowed(ProviderType.OPENROUTER, "openai/gpt-5.4")

            # Should have no restrictions
            assert not service.has_restrictions(ProviderType.OPENAI)
            assert not service.has_restrictions(ProviderType.GOOGLE)
            assert not service.has_restrictions(ProviderType.OPENROUTER)

    def test_load_single_model_restriction(self):
        """Test loading a single allowed model."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt-5.4"}):
            service = ModelRestrictionService()

            # Should only allow gpt-5.4
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4")
            assert not service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")

            # Google and OpenRouter should have no restrictions
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-pro")
            assert service.is_allowed(ProviderType.OPENROUTER, "anthropic/claude-opus-4.6")

    def test_load_multiple_models_restriction(self):
        """Test loading multiple allowed models."""
        with patch.dict(
            os.environ,
            {"OPENAI_ALLOWED_MODELS": "gpt-5.4-pro,gpt-5.4", "GOOGLE_ALLOWED_MODELS": "flash,pro"},
        ):
            # Instantiate providers so alias resolution for allow-lists is available
            openai_provider = OpenAIModelProvider(api_key="test-key")
            gemini_provider = GeminiModelProvider(api_key="test-key")

            from providers.registry import ModelProviderRegistry

            def fake_get_provider(provider_type, force_new=False):
                mapping = {
                    ProviderType.OPENAI: openai_provider,
                    ProviderType.GOOGLE: gemini_provider,
                }
                return mapping.get(provider_type)

            with patch.object(ModelProviderRegistry, "get_provider", side_effect=fake_get_provider):
                service = ModelRestrictionService()

                # Check OpenAI models
                assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")
                assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4")

                # Check Google models
                assert service.is_allowed(ProviderType.GOOGLE, "flash")
                assert service.is_allowed(ProviderType.GOOGLE, "pro")
                assert service.is_allowed(ProviderType.GOOGLE, "gemini-3.1-pro-preview")

    def test_case_insensitive_and_whitespace_handling(self):
        """Test that model names are case-insensitive and whitespace is trimmed."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": " GPT-5.4 , gpt-5.4-Pro "}):
            service = ModelRestrictionService()

            # Should work with any case
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4")
            assert service.is_allowed(ProviderType.OPENAI, "GPT-5.4")
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")
            assert service.is_allowed(ProviderType.OPENAI, "GPT-5.4-Pro")

    def test_empty_string_allows_all(self):
        """Test that empty string allows all models (same as unset)."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "", "GOOGLE_ALLOWED_MODELS": "flash"}):
            service = ModelRestrictionService()

            # OpenAI should allow all models (empty string = no restrictions)
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4")

            # Google should only allow flash (and its resolved name)
            assert service.is_allowed(ProviderType.GOOGLE, "flash")
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-flash", "flash")
            assert not service.is_allowed(ProviderType.GOOGLE, "pro")
            assert not service.is_allowed(ProviderType.GOOGLE, "gemini-3.1-pro-preview", "pro")

    def test_filter_models(self):
        """Test filtering a list of models based on restrictions."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt-5.4,gpt-5.4-pro"}):
            service = ModelRestrictionService()

            models = ["gpt-5.4-pro", "gpt-5.4", "gpt"]
            filtered = service.filter_models(ProviderType.OPENAI, models)

            assert filtered == ["gpt-5.4-pro", "gpt-5.4"]

    def test_get_allowed_models(self):
        """Test getting the set of allowed models."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt-5.4,gpt-5.4-pro"}):
            service = ModelRestrictionService()

            allowed = service.get_allowed_models(ProviderType.OPENAI)
            assert allowed == {"gpt-5.4", "gpt-5.4-pro"}

            # No restrictions for Google
            assert service.get_allowed_models(ProviderType.GOOGLE) is None

    def test_shorthand_names_in_restrictions(self):
        """Test that shorthand names work in restrictions."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt,gpt54", "GOOGLE_ALLOWED_MODELS": "flash,pro"}):
            # Instantiate providers so the registry can resolve aliases
            OpenAIModelProvider(api_key="test-key")
            GeminiModelProvider(api_key="test-key")

            service = ModelRestrictionService()

            # When providers check models, they pass both resolved and original names
            # OpenAI: 'gpt' shorthand allows gpt-5.4-pro
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro", "gpt")  # How providers actually call it
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")  # Canonical should also be allowed

            # OpenAI: 'gpt54' shorthand allows gpt-5.4
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4", "gpt54")
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4")

            # Google should allow both models via shorthands
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-flash", "flash")
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-3.1-pro-preview", "pro")

            # Also test that full names work when specified in restrictions
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4", "gpt54")  # Even with shorthand

    def test_validation_against_known_models(self, caplog):
        """Test validation warnings for unknown models."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt-5.4,gpt-5.4-pr0"}):  # Note the typo: gpt-5.4-pr0
            service = ModelRestrictionService()

            # Create mock provider with known models
            mock_provider = MagicMock()
            mock_provider.MODEL_CAPABILITIES = {
                "gpt-5.4-pro": {"context_window": 500000},
                "gpt-5.4": {"context_window": 500000},
            }
            mock_provider.list_models.return_value = ["gpt-5.4-pro", "gpt-5.4"]

            provider_instances = {ProviderType.OPENAI: mock_provider}
            service.validate_against_known_models(provider_instances)

            # Should have logged a warning about the typo
            assert "gpt-5.4-pr0" in caplog.text
            assert "not a recognized" in caplog.text

    def test_openrouter_model_restrictions(self):
        """Test OpenRouter model restrictions functionality."""
        with patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "opus,sonnet"}):
            service = ModelRestrictionService()

            # Should only allow specified OpenRouter models
            assert service.is_allowed(ProviderType.OPENROUTER, "opus")
            assert service.is_allowed(ProviderType.OPENROUTER, "sonnet")
            assert service.is_allowed(
                ProviderType.OPENROUTER, "anthropic/claude-opus-4.6", "opus"
            )  # With original name
            assert not service.is_allowed(ProviderType.OPENROUTER, "haiku")
            assert not service.is_allowed(ProviderType.OPENROUTER, "anthropic/claude-haiku-4.5")
            assert not service.is_allowed(ProviderType.OPENROUTER, "mistral-large")

            # Other providers should have no restrictions
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")
            assert service.is_allowed(ProviderType.GOOGLE, "pro")

            # Should have restrictions for OpenRouter
            assert service.has_restrictions(ProviderType.OPENROUTER)
            assert not service.has_restrictions(ProviderType.OPENAI)
            assert not service.has_restrictions(ProviderType.GOOGLE)

    def test_openrouter_filter_models(self):
        """Test filtering OpenRouter models based on restrictions."""
        with patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "opus,mistral"}):
            service = ModelRestrictionService()

            models = ["opus", "sonnet", "haiku", "mistral", "llama"]
            filtered = service.filter_models(ProviderType.OPENROUTER, models)

            assert filtered == ["opus", "mistral"]

    def test_combined_provider_restrictions(self):
        """Test that restrictions work correctly when set for multiple providers."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_ALLOWED_MODELS": "gpt-5.4-pro",
                "GOOGLE_ALLOWED_MODELS": "flash",
                "OPENROUTER_ALLOWED_MODELS": "opus,sonnet",
            },
        ):
            service = ModelRestrictionService()

            # OpenAI restrictions
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")
            assert not service.is_allowed(ProviderType.OPENAI, "gpt-5.4")

            # Google restrictions
            assert service.is_allowed(ProviderType.GOOGLE, "flash")
            assert not service.is_allowed(ProviderType.GOOGLE, "pro")

            # OpenRouter restrictions
            assert service.is_allowed(ProviderType.OPENROUTER, "opus")
            assert service.is_allowed(ProviderType.OPENROUTER, "sonnet")
            assert not service.is_allowed(ProviderType.OPENROUTER, "haiku")

            # All providers should have restrictions
            assert service.has_restrictions(ProviderType.OPENAI)
            assert service.has_restrictions(ProviderType.GOOGLE)
            assert service.has_restrictions(ProviderType.OPENROUTER)


class TestProviderIntegration:
    """Test integration with actual providers."""

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt-5.4"})
    def test_openai_provider_respects_restrictions(self):
        """Test that OpenAI provider respects restrictions."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = OpenAIModelProvider(api_key="test-key")

        # Should validate allowed model
        assert provider.validate_model_name("gpt-5.4")

        # Should not validate disallowed model
        assert not provider.validate_model_name("gpt-5.4-pro")

        # get_capabilities should raise for disallowed model
        with pytest.raises(ValueError) as exc_info:
            provider.get_capabilities("gpt-5.4-pro")
        assert "not allowed by restriction policy" in str(exc_info.value)

    @patch.dict(os.environ, {"GOOGLE_ALLOWED_MODELS": "gemini-2.5-flash,flash"})
    def test_gemini_provider_respects_restrictions(self):
        """Test that Gemini provider respects restrictions."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = GeminiModelProvider(api_key="test-key")

        # Should validate allowed models (both shorthand and full name allowed)
        assert provider.validate_model_name("flash")
        assert provider.validate_model_name("gemini-2.5-flash")

        # Should not validate disallowed model
        assert not provider.validate_model_name("pro")
        assert not provider.validate_model_name("gemini-3.1-pro-preview")

        # get_capabilities should raise for disallowed model
        with pytest.raises(ValueError) as exc_info:
            provider.get_capabilities("pro")
        assert "not allowed by restriction policy" in str(exc_info.value)

    @patch.dict(os.environ, {"GOOGLE_ALLOWED_MODELS": "flash"})
    def test_gemini_parameter_order_regression_protection(self):
        """Test that prevents regression of parameter order bug in is_allowed calls.

        This test specifically catches the bug where parameters were incorrectly
        passed as (provider, user_input, resolved_name) instead of
        (provider, resolved_name, user_input).

        The bug was subtle because the is_allowed method uses OR logic, so it
        worked in most cases by accident. This test creates a scenario where
        the parameter order matters.
        """
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = GeminiModelProvider(api_key="test-key")

        from providers.registry import ModelProviderRegistry

        with patch.object(ModelProviderRegistry, "get_provider", return_value=provider):
            # Test case: Only alias "flash" is allowed, not the full name
            # If parameters are in wrong order, this test will catch it

            # Should allow "flash" alias
            assert provider.validate_model_name("flash")

            # Should allow getting capabilities for "flash"
            capabilities = provider.get_capabilities("flash")
            assert capabilities.model_name == "gemini-2.5-flash"

            # Canonical form should also be allowed now that alias is on the allowlist
            assert provider.validate_model_name("gemini-2.5-flash")
            # Unrelated models remain blocked
            assert not provider.validate_model_name("pro")
            assert not provider.validate_model_name("gemini-3.1-pro-preview")

    @patch.dict(os.environ, {"GOOGLE_ALLOWED_MODELS": "gemini-2.5-flash"})
    def test_gemini_parameter_order_edge_case_full_name_only(self):
        """Test parameter order with only full name allowed, not alias.

        This is the reverse scenario - only the full canonical name is allowed,
        not the shorthand alias. This tests that the parameter order is correct
        when resolving aliases.
        """
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = GeminiModelProvider(api_key="test-key")

        # Should allow full name
        assert provider.validate_model_name("gemini-2.5-flash")

        # Should also allow alias that resolves to allowed full name
        # This works because is_allowed checks both resolved_name and original_name
        assert provider.validate_model_name("flash")

        # Should not allow "pro" alias
        assert not provider.validate_model_name("pro")
        assert not provider.validate_model_name("gemini-3.1-pro-preview")


class TestCustomProviderOpenRouterRestrictions:
    """Test custom provider integration with OpenRouter restrictions."""

    @patch.dict(
        os.environ,
        {"OPENROUTER_ALLOWED_MODELS": "opus,sonnet", "OPENROUTER_API_KEY": "test-key", "CUSTOM_ALLOWED_MODELS": ""},
    )
    def test_custom_provider_respects_openrouter_restrictions(self):
        """Test that custom provider correctly defers OpenRouter models to OpenRouter provider."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.custom import CustomProvider

        provider = CustomProvider(base_url="http://test.com/v1")

        # CustomProvider should NOT validate OpenRouter models - they should be deferred to OpenRouter
        assert not provider.validate_model_name("opus")
        assert not provider.validate_model_name("sonnet")
        assert not provider.validate_model_name("haiku")

        # Should still validate custom models defined in conf/custom_models.json
        assert provider.validate_model_name("gpt-5.4")

    @patch.dict(
        os.environ,
        {"OPENROUTER_ALLOWED_MODELS": "opus", "OPENROUTER_API_KEY": "test-key", "CUSTOM_ALLOWED_MODELS": ""},
    )
    def test_custom_provider_openrouter_capabilities_restrictions(self):
        """Test that custom provider's get_capabilities correctly handles OpenRouter models."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.custom import CustomProvider

        provider = CustomProvider(base_url="http://test.com/v1")

        # For OpenRouter models, CustomProvider should defer by raising
        with pytest.raises(ValueError):
            provider.get_capabilities("opus")

        # Should raise for disallowed OpenRouter model (still defers)
        with pytest.raises(ValueError):
            provider.get_capabilities("haiku")

        # Should still work for custom models
        capabilities = provider.get_capabilities("gpt-5.4")
        assert capabilities.provider == ProviderType.CUSTOM

    @patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "opus", "CUSTOM_ALLOWED_MODELS": ""}, clear=False)
    def test_custom_provider_no_openrouter_key_ignores_restrictions(self):
        """Test that when OpenRouter key is not set, cloud models are rejected regardless of restrictions."""
        # Make sure OPENROUTER_API_KEY is not set
        if "OPENROUTER_API_KEY" in os.environ:
            del os.environ["OPENROUTER_API_KEY"]
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.custom import CustomProvider

        provider = CustomProvider(base_url="http://test.com/v1")

        # Should not validate OpenRouter models when key is not available
        assert not provider.validate_model_name("opus")  # Even though it's in allowed list
        assert not provider.validate_model_name("haiku")

        # Should still validate custom models
        assert provider.validate_model_name("gpt-5.4")

    @patch.dict(
        os.environ,
        {"OPENROUTER_ALLOWED_MODELS": "", "OPENROUTER_API_KEY": "test-key", "CUSTOM_ALLOWED_MODELS": ""},
    )
    def test_custom_provider_empty_restrictions_allows_all_openrouter(self):
        """Test that custom provider correctly defers OpenRouter models regardless of restrictions."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.custom import CustomProvider

        provider = CustomProvider(base_url="http://test.com/v1")

        # CustomProvider should NOT validate OpenRouter models - they should be deferred to OpenRouter
        assert not provider.validate_model_name("opus")
        assert not provider.validate_model_name("sonnet")
        assert not provider.validate_model_name("haiku")


class TestRegistryIntegration:
    """Test integration with ModelProviderRegistry."""

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt", "GOOGLE_ALLOWED_MODELS": "flash"})
    def test_registry_with_shorthand_restrictions(self):
        """Test that registry handles shorthand restrictions correctly."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.registry import ModelProviderRegistry

        # Clear registry cache
        ModelProviderRegistry.clear_cache()

        # Get available models with restrictions
        # This test documents current behavior - get_available_models doesn't handle aliases
        ModelProviderRegistry.get_available_models(respect_restrictions=True)

        # Currently, this will be empty because get_available_models doesn't
        # recognize that "gpt" allows "gpt-5.4-pro"
        # This is a known limitation that should be documented

    @patch("providers.registry.ModelProviderRegistry.get_provider")
    def test_get_available_models_respects_restrictions(self, mock_get_provider):
        """Test that registry filters models based on restrictions."""
        from providers.registry import ModelProviderRegistry

        # Mock providers
        mock_openai = MagicMock()
        mock_openai.MODEL_CAPABILITIES = {
            "gpt-5.4-pro": {"context_window": 500000},
            "gpt-5.4": {"context_window": 500000},
        }
        mock_openai.get_provider_type.return_value = ProviderType.OPENAI

        def openai_list_models(
            *,
            respect_restrictions: bool = True,
            include_aliases: bool = True,
            lowercase: bool = False,
            unique: bool = False,
        ):
            from utils.model_restrictions import get_restriction_service

            restriction_service = get_restriction_service() if respect_restrictions else None
            models = []
            for model_name, config in mock_openai.MODEL_CAPABILITIES.items():
                if isinstance(config, str):
                    target_model = config
                    if restriction_service and not restriction_service.is_allowed(ProviderType.OPENAI, target_model):
                        continue
                    if include_aliases:
                        models.append(model_name)
                else:
                    if restriction_service and not restriction_service.is_allowed(ProviderType.OPENAI, model_name):
                        continue
                    models.append(model_name)
            if lowercase:
                models = [m.lower() for m in models]
            if unique:
                seen = set()
                ordered = []
                for name in models:
                    if name in seen:
                        continue
                    seen.add(name)
                    ordered.append(name)
                models = ordered
            return models

        mock_openai.list_models = MagicMock(side_effect=openai_list_models)

        def openai_get_capabilities(model_name: str):
            from types import SimpleNamespace

            return SimpleNamespace(model_name=model_name)

        mock_openai.get_capabilities = MagicMock(side_effect=openai_get_capabilities)

        mock_gemini = MagicMock()
        mock_gemini.MODEL_CAPABILITIES = {
            "gemini-3.1-pro-preview": {"context_window": 1048576},
            "gemini-2.5-flash": {"context_window": 1048576},
        }
        mock_gemini.get_provider_type.return_value = ProviderType.GOOGLE

        def gemini_list_models(
            *,
            respect_restrictions: bool = True,
            include_aliases: bool = True,
            lowercase: bool = False,
            unique: bool = False,
        ):
            from utils.model_restrictions import get_restriction_service

            restriction_service = get_restriction_service() if respect_restrictions else None
            models = []
            for model_name, config in mock_gemini.MODEL_CAPABILITIES.items():
                if isinstance(config, str):
                    target_model = config
                    if restriction_service and not restriction_service.is_allowed(ProviderType.GOOGLE, target_model):
                        continue
                    if include_aliases:
                        models.append(model_name)
                else:
                    if restriction_service and not restriction_service.is_allowed(ProviderType.GOOGLE, model_name):
                        continue
                    models.append(model_name)
            if lowercase:
                models = [m.lower() for m in models]
            if unique:
                seen = set()
                ordered = []
                for name in models:
                    if name in seen:
                        continue
                    seen.add(name)
                    ordered.append(name)
                models = ordered
            return models

        mock_gemini.list_models = MagicMock(side_effect=gemini_list_models)

        def get_provider_side_effect(provider_type):
            if provider_type == ProviderType.OPENAI:
                return mock_openai
            elif provider_type == ProviderType.GOOGLE:
                return mock_gemini
            return None

        mock_get_provider.side_effect = get_provider_side_effect

        # Set up registry with providers
        registry = ModelProviderRegistry()
        registry._providers = {
            ProviderType.OPENAI: type(mock_openai),
            ProviderType.GOOGLE: type(mock_gemini),
        }

        with patch.dict(
            os.environ,
            {"OPENAI_ALLOWED_MODELS": "gpt-5.4", "GOOGLE_ALLOWED_MODELS": "gemini-2.5-flash"},
        ):
            # Clear cached restriction service
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            available = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            # Should only include allowed models
            assert "gpt-5.4" in available
            assert "gpt-5.4-pro" not in available
            assert "gemini-2.5-flash" in available
            assert "gemini-3.1-pro-preview" not in available


class TestShorthandRestrictions:
    """Test that shorthand model names work correctly in restrictions."""

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt", "GOOGLE_ALLOWED_MODELS": "flash"})
    def test_providers_validate_shorthands_correctly(self):
        """Test that providers correctly validate shorthand names."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Test OpenAI provider
        openai_provider = OpenAIModelProvider(api_key="test-key")
        gemini_provider = GeminiModelProvider(api_key="test-key")

        from providers.registry import ModelProviderRegistry

        def registry_side_effect(provider_type, force_new=False):
            mapping = {
                ProviderType.OPENAI: openai_provider,
                ProviderType.GOOGLE: gemini_provider,
            }
            return mapping.get(provider_type)

        with patch.object(ModelProviderRegistry, "get_provider", side_effect=registry_side_effect):
            assert openai_provider.validate_model_name("gpt")  # Should work with shorthand
            assert openai_provider.validate_model_name("gpt-5.4-pro")  # Canonical resolved from shorthand
            assert not openai_provider.validate_model_name("gpt-5.4")  # Unrelated model still blocked

            # Test Gemini provider
            assert gemini_provider.validate_model_name("flash")  # Should work with shorthand
            assert gemini_provider.validate_model_name("gemini-2.5-flash")  # Canonical allowed
            assert not gemini_provider.validate_model_name("pro")  # Not allowed

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt54,gpt"})
    def test_multiple_shorthands_for_same_model(self):
        """Test that multiple shorthands work correctly."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        openai_provider = OpenAIModelProvider(api_key="test-key")

        # Both shorthands should work
        assert openai_provider.validate_model_name("gpt")  # gpt -> gpt-5.4-pro
        assert openai_provider.validate_model_name("gpt54")  # gpt54 -> gpt-5.4

        # Resolved names should be allowed when their shorthands are present
        assert openai_provider.validate_model_name("gpt-5.4-pro")  # Allowed via shorthand
        assert openai_provider.validate_model_name("gpt-5.4")  # Allowed via shorthand

        # Other models should not work
        assert not openai_provider.validate_model_name("gpt-4")
        assert not openai_provider.validate_model_name("gpt-5")

    @patch.dict(
        os.environ,
        {"OPENAI_ALLOWED_MODELS": "gpt,gpt-5.4-pro", "GOOGLE_ALLOWED_MODELS": "flash,gemini-2.5-flash"},
    )
    def test_both_shorthand_and_full_name_allowed(self):
        """Test that we can allow both shorthand and full names."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # OpenAI - both gpt and gpt-5.4-pro are allowed
        openai_provider = OpenAIModelProvider(api_key="test-key")
        assert openai_provider.validate_model_name("gpt")
        assert openai_provider.validate_model_name("gpt-5.4-pro")

        # Gemini - both flash and full name are allowed
        gemini_provider = GeminiModelProvider(api_key="test-key")
        assert gemini_provider.validate_model_name("flash")
        assert gemini_provider.validate_model_name("gemini-2.5-flash")


class TestAutoModeWithRestrictions:
    """Test auto mode behavior with restrictions."""

    @patch("providers.registry.ModelProviderRegistry.get_provider")
    def test_fallback_model_respects_restrictions(self, mock_get_provider):
        """Test that fallback model selection respects restrictions."""
        from providers.registry import ModelProviderRegistry
        from tools.models import ToolModelCategory

        # Mock providers
        mock_openai = MagicMock()
        mock_openai.MODEL_CAPABILITIES = {
            "gpt-5.4-pro": {"context_window": 500000},
            "gpt-5.4": {"context_window": 500000},
        }
        mock_openai.get_provider_type.return_value = ProviderType.OPENAI

        def openai_list_models(
            *,
            respect_restrictions: bool = True,
            include_aliases: bool = True,
            lowercase: bool = False,
            unique: bool = False,
        ):
            from utils.model_restrictions import get_restriction_service

            restriction_service = get_restriction_service() if respect_restrictions else None
            models = []
            for model_name, config in mock_openai.MODEL_CAPABILITIES.items():
                if isinstance(config, str):
                    target_model = config
                    if restriction_service and not restriction_service.is_allowed(ProviderType.OPENAI, target_model):
                        continue
                    if include_aliases:
                        models.append(model_name)
                else:
                    if restriction_service and not restriction_service.is_allowed(ProviderType.OPENAI, model_name):
                        continue
                    models.append(model_name)
            if lowercase:
                models = [m.lower() for m in models]
            if unique:
                seen = set()
                ordered = []
                for name in models:
                    if name in seen:
                        continue
                    seen.add(name)
                    ordered.append(name)
                models = ordered
            return models

        mock_openai.list_models = MagicMock(side_effect=openai_list_models)

        def openai_get_capabilities(model_name: str):
            from types import SimpleNamespace

            return SimpleNamespace(model_name=model_name)

        mock_openai.get_capabilities = MagicMock(side_effect=openai_get_capabilities)

        # Add get_preferred_model method to mock to match new implementation
        def get_preferred_model(category, allowed_models):
            # Simple preference logic for testing - just return first allowed model
            return allowed_models[0] if allowed_models else None

        mock_openai.get_preferred_model = get_preferred_model

        def get_provider_side_effect(provider_type):
            if provider_type == ProviderType.OPENAI:
                return mock_openai
            return None

        mock_get_provider.side_effect = get_provider_side_effect

        # Set up registry
        registry = ModelProviderRegistry()
        registry._providers = {ProviderType.OPENAI: type(mock_openai)}

        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "gpt-5.4"}):
            # Clear cached restriction service
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            # Should pick gpt-5.4 when it is the only allowed OpenAI model
            model = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)
            assert model == "gpt-5.4"

    def test_fallback_with_shorthand_restrictions(self, monkeypatch):
        """Test fallback model selection with shorthand restrictions."""
        # Use monkeypatch to set environment variables with automatic cleanup
        monkeypatch.setenv("OPENAI_ALLOWED_MODELS", "gpt54")
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Clear caches and reset registry
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry
        from tools.models import ToolModelCategory

        utils.model_restrictions._restriction_service = None

        # Store original providers for restoration
        registry = ModelProviderRegistry()
        original_providers = registry._providers.copy()
        original_initialized = registry._initialized_providers.copy()

        try:
            # Clear registry and register only OpenAI and Gemini providers
            ModelProviderRegistry._instance = None
            from providers.gemini import GeminiModelProvider
            from providers.openai import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Even with a shorthand restriction, fallback should work if provider handles it correctly
            # This tests the real-world scenario
            model = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)

            # The fallback will depend on how get_available_models handles aliases
            # When "gpt54" is allowed, it resolves to gpt-5.4 for selection.
            assert model == "gpt-5.4"
        finally:
            # Restore original registry state
            registry = ModelProviderRegistry()
            registry._providers.clear()
            registry._initialized_providers.clear()
            registry._providers.update(original_providers)
            registry._initialized_providers.update(original_initialized)
