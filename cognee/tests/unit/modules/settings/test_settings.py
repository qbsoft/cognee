"""Unit tests for cognee.modules.settings module."""
import pytest
from enum import Enum

from cognee.modules.settings.get_settings import (
    ConfigChoice,
    ModelName,
    LLMConfig,
    VectorDBConfig,
    SettingsDict,
)


class TestConfigChoice:
    """Tests for the ConfigChoice model."""

    def test_config_choice_creation(self):
        """Test ConfigChoice basic creation."""
        choice = ConfigChoice(value="openai", label="OpenAI")
        assert choice.value == "openai"
        assert choice.label == "OpenAI"


class TestModelName:
    """Tests for the ModelName enum."""

    def test_model_name_is_enum(self):
        """Test ModelName is an Enum."""
        assert issubclass(ModelName, Enum)

    def test_model_name_all_providers_exist(self):
        """Test all expected model providers are defined."""
        expected = ["openai", "ollama", "anthropic", "gemini", "mistral"]
        for provider in expected:
            assert hasattr(ModelName, provider)

    def test_model_name_from_string(self):
        """Test ModelName creation from string value."""
        assert ModelName("openai") == ModelName.openai


class TestLLMConfig:
    """Tests for the LLMConfig model."""

    def test_llm_config_creation(self):
        """Test LLMConfig basic creation."""
        config = LLMConfig(
            api_key="test-key", model="gpt-4o", provider="openai",
            endpoint=None, api_version=None, models={}, providers=[]
        )
        assert config.api_key == "test-key"
        assert config.model == "gpt-4o"
        assert config.provider == "openai"


class TestVectorDBConfig:
    """Tests for the VectorDBConfig model."""

    def test_vector_db_config_creation(self):
        """Test VectorDBConfig basic creation."""
        config = VectorDBConfig(
            api_key="test-key", url="http://localhost",
            provider="lancedb", providers=[]
        )
        assert config.provider == "lancedb"


class TestSettingsDict:
    """Tests for the SettingsDict model."""

    def test_settings_dict_creation(self):
        """Test SettingsDict basic creation."""
        llm = LLMConfig(
            api_key="k", model="m", provider="openai",
            endpoint=None, api_version=None, models={}, providers=[]
        )
        vector = VectorDBConfig(
            api_key="k", url="http://localhost", provider="lancedb", providers=[]
        )
        settings = SettingsDict(llm=llm, vector_db=vector)
        assert settings.llm.provider == "openai"
        assert settings.vector_db.provider == "lancedb"
