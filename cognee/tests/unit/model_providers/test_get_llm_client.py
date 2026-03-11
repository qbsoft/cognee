"""Unit tests for get_llm_client with override parameters."""

import pytest
import inspect


class TestGetLlmClientOverrides:
    """Tests for the new override parameters in get_llm_client."""

    def test_function_signature_has_override_params(self):
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import get_llm_client

        sig = inspect.signature(get_llm_client)
        params = list(sig.parameters.keys())
        assert "api_key_override" in params
        assert "endpoint_override" in params
        assert "provider_override" in params
        assert "model_override" in params

    def test_get_llm_client_for_user_function_exists(self):
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import get_llm_client_for_user
        assert inspect.iscoroutinefunction(get_llm_client_for_user)

    def test_get_llm_client_for_user_signature(self):
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import get_llm_client_for_user
        sig = inspect.signature(get_llm_client_for_user)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "task_type" in params

    def test_llm_provider_enum_values(self):
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import LLMProvider
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.OLLAMA.value == "ollama"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.CUSTOM.value == "custom"
        assert LLMProvider.GEMINI.value == "gemini"
        assert LLMProvider.MISTRAL.value == "mistral"

    def test_get_llm_client_callable(self):
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import get_llm_client
        assert callable(get_llm_client)

    def test_override_defaults_are_none(self):
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import get_llm_client
        sig = inspect.signature(get_llm_client)
        assert sig.parameters["api_key_override"].default is None
        assert sig.parameters["endpoint_override"].default is None
        assert sig.parameters["provider_override"].default is None
        assert sig.parameters["model_override"].default is None
