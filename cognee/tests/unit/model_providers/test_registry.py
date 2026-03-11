"""Unit tests for the model provider registry."""

import pytest
from cognee.infrastructure.llm.providers.registry import (
    get_all_providers,
    get_provider,
    get_providers_by_category,
    ProviderDefinition,
    ModelInfo,
    ConfigField,
)


class TestProviderRegistry:
    """Tests for the in-memory provider registry."""

    def test_get_all_providers_returns_list(self):
        providers = get_all_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_all_providers_are_provider_definitions(self):
        for p in get_all_providers():
            assert isinstance(p, ProviderDefinition)

    def test_provider_has_required_fields(self):
        for p in get_all_providers():
            assert p.id, f"Provider missing id: {p}"
            assert p.name, f"Provider {p.id} missing name"
            assert p.name_en, f"Provider {p.id} missing name_en"
            assert p.category in ("cloud_cn", "cloud_intl", "local"), (
                f"Provider {p.id} has invalid category: {p.category}"
            )

    def test_provider_ids_unique(self):
        ids = [p.id for p in get_all_providers()]
        assert len(ids) == len(set(ids)), f"Duplicate provider IDs found: {ids}"

    def test_get_provider_by_id(self):
        providers = get_all_providers()
        for p in providers:
            found = get_provider(p.id)
            assert found is not None
            assert found.id == p.id

    def test_get_provider_nonexistent(self):
        assert get_provider("nonexistent_provider_xyz") is None

    def test_get_providers_by_category_cloud_cn(self):
        cn_providers = get_providers_by_category("cloud_cn")
        assert len(cn_providers) > 0
        for p in cn_providers:
            assert p.category == "cloud_cn"

    def test_get_providers_by_category_cloud_intl(self):
        intl_providers = get_providers_by_category("cloud_intl")
        assert len(intl_providers) > 0
        for p in intl_providers:
            assert p.category == "cloud_intl"

    def test_get_providers_by_category_local(self):
        local_providers = get_providers_by_category("local")
        assert len(local_providers) > 0
        for p in local_providers:
            assert p.category == "local"

    def test_get_providers_by_category_empty(self):
        result = get_providers_by_category("nonexistent_category")
        assert result == []

    def test_dashscope_provider_exists(self):
        p = get_provider("dashscope")
        assert p is not None
        assert "DashScope" in p.name_en
        assert p.category == "cloud_cn"
        assert p.is_openai_compatible is True
        assert "chat" in p.capabilities

    def test_ollama_provider_exists(self):
        p = get_provider("ollama")
        assert p is not None
        assert p.category == "local"
        assert p.auth_type == "none"
        assert p.is_openai_compatible is True

    def test_openai_provider_exists(self):
        p = get_provider("openai")
        assert p is not None
        assert p.category == "cloud_intl"
        assert p.auth_type == "api_key"

    def test_provider_models_are_model_info(self):
        for p in get_all_providers():
            for m in p.default_models:
                assert isinstance(m, ModelInfo)
                assert m.id, f"Model missing id in provider {p.id}"
                assert m.name, f"Model {m.id} missing name in provider {p.id}"

    def test_provider_config_fields_are_config_field(self):
        for p in get_all_providers():
            for f in p.config_fields:
                assert isinstance(f, ConfigField)
                assert f.key, f"ConfigField missing key in provider {p.id}"

    def test_openai_compatible_providers_have_base_url(self):
        for p in get_all_providers():
            # "custom" provider intentionally has no default_base_url (user must provide)
            if p.is_openai_compatible and p.auth_type == "api_key" and p.id != "custom":
                assert p.default_base_url, (
                    f"OpenAI-compatible provider {p.id} should have default_base_url"
                )

    def test_local_providers_have_base_url(self):
        for p in get_providers_by_category("local"):
            # "custom" provider intentionally has no default (user provides their own)
            if p.id == "custom":
                continue
            assert p.default_base_url, (
                f"Local provider {p.id} should have default_base_url"
            )
