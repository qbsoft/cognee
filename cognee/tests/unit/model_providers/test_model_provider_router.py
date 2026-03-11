"""Unit tests for the model provider API router."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from cognee.api.v1.model_providers.routers.model_provider_router import (
    get_model_provider_router,
    ProviderConfigInput,
    DefaultModelInput,
    DefaultModelsInput,
    ConnectionTestInput,
    _serialize_provider,
)


class TestDTOs:
    """Tests for request/response DTOs."""

    def test_provider_config_input_defaults(self):
        dto = ProviderConfigInput()
        assert dto.api_key == ""
        assert dto.base_url == ""
        assert dto.custom_params == {}

    def test_provider_config_input_with_values(self):
        dto = ProviderConfigInput(
            api_key="sk-test",
            base_url="https://api.example.com",
            custom_params={"temperature": 0.7},
        )
        assert dto.api_key == "sk-test"
        assert dto.base_url == "https://api.example.com"
        assert dto.custom_params == {"temperature": 0.7}

    def test_default_model_input(self):
        dto = DefaultModelInput(provider_id="dashscope", model_id="qwen-plus")
        assert dto.provider_id == "dashscope"
        assert dto.model_id == "qwen-plus"

    def test_default_models_input_optional(self):
        dto = DefaultModelsInput()
        assert dto.chat is None
        assert dto.extraction is None
        assert dto.embedding is None

    def test_default_models_input_partial(self):
        dto = DefaultModelsInput(
            chat=DefaultModelInput(provider_id="dashscope", model_id="qwen-plus"),
        )
        assert dto.chat is not None
        assert dto.extraction is None

    def test_connection_test_input(self):
        dto = ConnectionTestInput(api_key="sk-test", base_url="https://api.example.com")
        assert dto.api_key == "sk-test"


class TestSerializeProvider:
    """Tests for the _serialize_provider helper."""

    def test_serialize_without_user_config(self):
        from cognee.infrastructure.llm.providers.registry import get_provider

        prov = get_provider("dashscope")
        result = _serialize_provider(prov)
        assert result["id"] == "dashscope"
        assert result["name"] == prov.name
        assert result["is_configured"] is False
        assert result["is_enabled"] is False
        assert result["api_key_preview"] == ""
        assert isinstance(result["models"], list)
        assert isinstance(result["config_fields"], list)

    def test_serialize_with_user_config(self):
        from cognee.infrastructure.llm.providers.registry import get_provider
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig

        prov = get_provider("openai")
        config = UserModelConfig(
            id=uuid4(),
            user_id=uuid4(),
            provider_id="openai",
            enabled=True,
        )
        config.set_api_key("sk-test-key-xyz")

        result = _serialize_provider(prov, {"openai": config})
        assert result["is_configured"] is True
        assert result["is_enabled"] is True
        assert "****" in result["api_key_preview"]

    def test_serialize_models_structure(self):
        from cognee.infrastructure.llm.providers.registry import get_provider

        prov = get_provider("dashscope")
        result = _serialize_provider(prov)
        for m in result["models"]:
            assert "id" in m
            assert "name" in m
            assert "capabilities" in m
            assert "max_tokens" in m
            assert "is_default" in m

    def test_serialize_config_fields_structure(self):
        from cognee.infrastructure.llm.providers.registry import get_provider

        prov = get_provider("dashscope")
        result = _serialize_provider(prov)
        for f in result["config_fields"]:
            assert "key" in f
            assert "label" in f
            assert "type" in f
            assert "required" in f


class TestRouterFactory:
    """Tests for the router factory function."""

    def test_get_model_provider_router_returns_api_router(self):
        from fastapi import APIRouter

        router = get_model_provider_router()
        assert isinstance(router, APIRouter)

    def test_router_has_expected_routes(self):
        router = get_model_provider_router()
        route_paths = [r.path for r in router.routes]
        assert "" in route_paths  # GET /
        assert "/user/defaults" in route_paths  # GET, PUT
        assert "/{provider_id}" in route_paths  # GET
        assert "/{provider_id}/config" in route_paths  # POST, DELETE
        assert "/{provider_id}/test" in route_paths  # POST
