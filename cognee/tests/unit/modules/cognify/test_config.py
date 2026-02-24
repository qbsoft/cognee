"""Unit tests for cognee.modules.cognify.config module."""
import pytest
from unittest.mock import patch

from cognee.modules.cognify.config import CognifyConfig, get_cognify_config
from cognee.shared.data_models import DefaultContentPrediction, SummarizedContent


class TestCognifyConfig:
    """Tests for the CognifyConfig class."""

    def test_cognify_config_default_classification_model(self):
        """Test CognifyConfig has default classification model."""
        config = CognifyConfig()

        assert config.classification_model == DefaultContentPrediction

    def test_cognify_config_default_summarization_model(self):
        """Test CognifyConfig has default summarization model."""
        config = CognifyConfig()

        assert config.summarization_model == SummarizedContent

    def test_cognify_config_custom_classification_model(self):
        """Test CognifyConfig accepts custom classification model."""
        class CustomClassification:
            pass

        config = CognifyConfig(classification_model=CustomClassification)

        assert config.classification_model == CustomClassification

    def test_cognify_config_custom_summarization_model(self):
        """Test CognifyConfig accepts custom summarization model."""
        class CustomSummarization:
            pass

        config = CognifyConfig(summarization_model=CustomSummarization)

        assert config.summarization_model == CustomSummarization

    def test_cognify_config_to_dict(self):
        """Test CognifyConfig.to_dict() returns correct dictionary."""
        config = CognifyConfig()
        result = config.to_dict()

        assert isinstance(result, dict)
        assert "classification_model" in result
        assert "summarization_model" in result
        assert result["classification_model"] == DefaultContentPrediction
        assert result["summarization_model"] == SummarizedContent

    def test_cognify_config_to_dict_with_custom_models(self):
        """Test CognifyConfig.to_dict() with custom models."""
        class CustomClassification:
            pass

        class CustomSummarization:
            pass

        config = CognifyConfig(
            classification_model=CustomClassification,
            summarization_model=CustomSummarization,
        )
        result = config.to_dict()

        assert result["classification_model"] == CustomClassification
        assert result["summarization_model"] == CustomSummarization

    def test_cognify_config_extra_fields_allowed(self):
        """Test CognifyConfig allows extra fields due to extra='allow'."""
        config = CognifyConfig(custom_field="custom_value")

        assert hasattr(config, "custom_field")
        assert config.custom_field == "custom_value"


class TestGetCognifyConfig:
    """Tests for the get_cognify_config function."""

    def test_get_cognify_config_returns_config_instance(self):
        """Test get_cognify_config returns CognifyConfig instance."""
        # Clear cache first
        get_cognify_config.cache_clear()

        config = get_cognify_config()

        assert isinstance(config, CognifyConfig)

    def test_get_cognify_config_is_cached(self):
        """Test get_cognify_config returns same cached instance."""
        # Clear cache first
        get_cognify_config.cache_clear()

        config1 = get_cognify_config()
        config2 = get_cognify_config()

        assert config1 is config2

    def test_get_cognify_config_cache_info(self):
        """Test get_cognify_config cache statistics."""
        # Clear cache first
        get_cognify_config.cache_clear()

        get_cognify_config()
        get_cognify_config()
        get_cognify_config()

        cache_info = get_cognify_config.cache_info()
        assert cache_info.hits >= 2
        assert cache_info.misses >= 1
